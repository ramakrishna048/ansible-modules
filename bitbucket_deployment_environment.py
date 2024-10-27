#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import requests

def run_module():
    module_args = dict(
        workspace=dict(type='str', required=True),
        repo_slug=dict(type='str', required=True),
        name=dict(type='str', required=True),
        environment_type=dict(type='str', required=True),
        state=dict(type='str', default='present', choices=['present', 'absent']),
        username=dict(type='str', required=True),
        password=dict(type='str', required=True, no_log=True),
    )

    result = dict(
        changed=False,
        uuid='',
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    if module.check_mode:
        module.exit_json(**result)

    # Logic to get or create the environment
    base_url = f"https://api.bitbucket.org/2.0/repositories/{module.params['workspace']}/{module.params['repo_slug']}/environments"
    auth = (module.params['username'], module.params['password'])

    # Check if environment exists
    response = requests.get(base_url, auth=auth)
    environments = response.json().get('values', [])
    existing_env = next((env for env in environments if env['name'] == module.params['name']), None)

    if existing_env:
        result['uuid'] = existing_env['uuid']
    elif module.params['state'] == 'present':
        # Create environment
        data = {
            'name': module.params['name'],
            'environment_type': {'name': module.params['environment_type']}
        }
        response = requests.post(base_url, json=data, auth=auth)
        if response.status_code == 201:
            result['changed'] = True
            result['uuid'] = response.json()['uuid']
        else:
            module.fail_json(msg=f"Failed to create environment: {response.text}", **result)

    module.exit_json(**result)

if __name__ == '__main__':
    run_module()