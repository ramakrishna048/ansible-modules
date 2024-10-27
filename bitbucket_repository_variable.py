#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import requests
import json

def get_all_variables(base_url, auth):
    all_variables = []
    url = f"{base_url}?pagelen=100"
    while url:
        response = requests.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        all_variables.extend(data.get('values', []))
        url = data.get('next')
    return all_variables

def main():
    module = AnsibleModule(
        argument_spec=dict(
            workspace=dict(required=True, type='str'),
            repo_slug=dict(required=True, type='str'),
            username=dict(required=True, type='str'),
            password=dict(required=True, type='str', no_log=True),
            variable_name=dict(required=True, type='str'),
            variable_value=dict(required=True, type='str'),
            secured=dict(type='bool', default=False),
            state=dict(type='str', default='present', choices=['present', 'absent']),
        ),
        supports_check_mode=True
    )

    params = module.params
    
    base_url = f"https://api.bitbucket.org/2.0/repositories/{params['workspace']}/{params['repo_slug']}/pipelines_config/variables"

    # Get all variables
    try:
        all_variables = get_all_variables(base_url, auth=(params['username'], params['password']))
        module.debug(f"All variables: {json.dumps(all_variables, indent=2)}")
    except requests.exceptions.RequestException as e:
        module.fail_json(msg=f"Error fetching variables: {str(e)}")

    # Find the target variable
    existing_variable = next((var for var in all_variables if var['key'] == params['variable_name']), None)

    module.debug(f"Existing variable: {json.dumps(existing_variable, indent=2)}")
    module.debug(f"Searching for variable name: {params['variable_name']}")

    # Determine if changes are needed
    if existing_variable:
        if params['secured']:
            # For secured variables, we can't compare values, so we'll always update
            changed = True
        else:
            changed = existing_variable.get('value') != params['variable_value'] or existing_variable.get('secured', False) != params['secured']
    else:
        changed = params['state'] == 'present'

    # Prepare result message and diff
    result = {
        "changed": changed,
        "variable_name": params['variable_name'],
        "new_value": "**********" if params['secured'] else params['variable_value'],
        "new_secured": params['secured']
    }

    diff = {
        'before': {
            'variable_name': params['variable_name'],
            'value': "**********" if existing_variable and existing_variable.get('secured') else (existing_variable.get('value', '') if existing_variable else ''),
            'secured': existing_variable.get('secured', False) if existing_variable else False
        },
        'after': {
            'variable_name': params['variable_name'],
            'value': "**********" if params['secured'] else params['variable_value'],
            'secured': params['secured']
        }
    }

    if existing_variable:
        result["existing_value"] = "**********" if existing_variable.get('secured') else existing_variable.get('value', '')
        result["existing_secured"] = existing_variable.get('secured', False)
        msg = f"Variable '{params['variable_name']}' would be updated"
    else:
        msg = f"Variable '{params['variable_name']}' would be created"

    if changed:
        if params['secured']:
            msg += f": [secured value] -> [new secured value]"
        else:
            msg += f": {result.get('existing_value', '')} -> {result['new_value']}"
    else:
        msg = f"No changes required for variable '{params['variable_name']}'"

    module.debug(f"Result: {json.dumps(result, indent=2)}")
    module.debug(f"Diff: {json.dumps(diff, indent=2)}")

    # If check mode, return the change status without making changes
    if module.check_mode:
        module.exit_json(changed=changed, msg=f"Check mode: {msg}", result=result, diff=diff)

    # If not in check mode and changes are needed, make the API request
    if changed and params['state'] == 'present':
        try:
            new_data = {
                "key": params['variable_name'],
                "value": params['variable_value'],
                "secured": params['secured']
            }
            if existing_variable:
                # Update existing variable
                url = f"{base_url}/{existing_variable['uuid']}"
                module.debug(f"Updating variable. URL: {url}")
                response = requests.put(url, json=new_data, auth=(params['username'], params['password']))
            else:
                # Create new variable
                module.debug(f"Creating new variable. URL: {base_url}")
                response = requests.post(base_url, json=new_data, auth=(params['username'], params['password']))
            
            module.debug(f"API response status code: {response.status_code}")
            module.debug(f"API response content: {response.text}")
            
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            module.fail_json(msg=f"Error creating/updating variable: {str(e)}")

        module.exit_json(changed=True, msg=f"{msg} successfully", result=result, diff=diff)
    elif changed and params['state'] == 'absent':
        try:
            # Delete variable
            url = f"{base_url}/{existing_variable['uuid']}"
            module.debug(f"Deleting variable. URL: {url}")
            response = requests.delete(url, auth=(params['username'], params['password']))
            
            module.debug(f"API response status code: {response.status_code}")
            
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            module.fail_json(msg=f"Error deleting variable: {str(e)}")

        module.exit_json(changed=True, msg=f"{msg} successfully", result=result, diff=diff)
    else:
        module.exit_json(changed=False, msg=msg, result=result, diff=diff)

if __name__ == '__main__':
    main()