"""
This integration script checks to see if the global configuration for GMS was changed and if
a change is found an email with what changed is sent to the GMS admins
"""

import sys
import time
import datetime
import logging
import os
import collections
import shutil
import subprocess
import json
import ast
import requests
import git
import tempfile

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from os.path import expanduser
from git import Repo
from git import Git

def parse_arguments():
    """ This method returns the returns all a named tuple with all
    of the values retrieved from the Azure Key Vault
    """
    arg_dict = {}
    arg_dict['azure_vault_url'] = os.environ['AZURE_VAULT_URL']

    # create the service principle credentials used to authenticate the client
    credential = DefaultAzureCredential()

    # create the client using the created credentials
    client = SecretClient(vault_url=arg_dict['azure_vault_url'], credential=credential)

    func_fluxx = get_value(client, 'FUNC-FLUXX')
    func_mail = get_value(client, 'FUNC-MAIL')
    logging.info(json.dumps(arg_dict, indent=4))

    #Add variables that should not be logged after the log the environment variables
    arg_dict['func_fluxx'] = func_fluxx
    arg_dict['func_mail'] = func_mail
    arg_dict['source_repository'] = os.environ.get('SOURCE_REPOSITORY', 'fluxx-audit')
    arg_dict['source_library'] = os.environ.get('SOURCE_LIBRARY', 'macfound')
    arg_dict['source_folder'] = os.environ.get('SOURCE_FOLDER', 'configuration_audit')
    arg_dict['source_configuration_id'] = os.environ.get('SOURCE_CONFIGURATION_ID', '47')
    arg_dict['gms_per_page'] = os.environ.get('GMS_PER_PAGE', '100')
    arg_dict['env'] = os.environ.get('ENVIRONMENT', 'dev')
    arg_dict['active_branch'] = os.environ.get('ACTIVE_BRANCH', 'dev')
    arg_dict['is_debug'] = ast.literal_eval(os.environ["IS_DEBUG"])    
    arg_dict['temp_dir'] = tempfile.gettempdir()

    return collections.namedtuple('GenericDict', arg_dict.keys())(**arg_dict)

def get_value(client, key):
    """ This retrieves the secret value from the key vault for a specific key
    Args:
        client (SecretClient): This os the azure keyvault secret client to retrieve secrets
        key (str): The key used to retrieve the value from the client
    """

    return  client.get_secret(key).value

def get_access_token(args):
    """ This mehtod retrieves the access token required for Fluxx API calls.
    """
    try:
        url = "https://func-fluxx-" + args.env + ".azurewebsites.net/api/get_access_token"
        results = requests.post(url, headers={'x-functions-key': args.func_fluxx})
        json_results = results.json()
    except Exception as exc:
        logging.info("Failure in get_access_token.  Reason: %s", results.reason + " " + str(exc))
        sys.exit("Failure in get_access_token.")
    return json_results['access_token']

#==============================================================
# Job Specifc Functions
#==============================================================
def get_gms_updated_by_name(args, access_token, updated_by_id):
    """ This method retrieves the current configuration from GMS
    Args:
        args (namedtuple): This parameter represents the dictionary
		    that will hold all the arguments passed in and retrieved from PMP
    """
    try:
        url = "https://func-fluxx-" + args.env + ".azurewebsites.net/api/get_fluxx_object"
        body_parameters = {
            "model_type": "user/" + str(updated_by_id),
            "access_token": access_token,
            "json_string": "cols=[\"first_name\",\"last_name\",\"email\"]",            
            "gms_per_page": args.gms_per_page,
            "is_json_props_ordered": True
            }
        results = requests.post(url, headers={'x-functions-key': args.func_fluxx, }, \
        data=json.dumps(body_parameters))
    except:
        logging.info("Failure in get_gms_updated_by_name.  Reason: %s", results.reason)
        sys.exit("Failure in get_gms_updated_by_name.")
    return results.json()

def get_gms_config(args, access_token):
    """ This method retrieves the current configuration from GMS
    Args:
        args (namedtuple): This parameter represents the dictionary
		    that will hold all the arguments passed in and retrieved from PMP
    """
    try:
        url = "https://func-fluxx-" + args.env + ".azurewebsites.net/api/get_fluxx_object"
        body_parameters = {
            "model_type": "client_configuration/" + args.source_configuration_id,
            "access_token": access_token,
            "json_string": "all_core=1&all_dynamic=1",            
            "gms_per_page": args.gms_per_page,
            "is_json_props_ordered": True
            }
        results = requests.post(url, headers={'x-functions-key': args.func_fluxx, }, \
        data=json.dumps(body_parameters))
    except:
        logging.info("Failure in get_gms_config.  Reason: %s", results.reason)
        sys.exit("Failure in get_gms_config.")

    results = results.json()["client_configuration"]
    
    results['user'] = get_gms_updated_by_name(args, access_token, results['updated_by_id'])
    
    return results

def cleanup(args):
    """This method removes the cloned repository from the filesystem
    Args:
        args (namedtuple): This parameter represents the dictionary
		    that will hold all the arguments passed in and retrieved from PMP
    """

    logging.info("Removing Old Repository From Filesystem")
    repo_dir = os.path.join(args.temp_dir,args.source_repository).replace(os.sep, '/')
    if os.path.exists(repo_dir):
        os.system('rmdir /S /Q "{}"'.format(repo_dir))

def clone_repository(args):
    """This method clones the repository with a depth of 1
    Args:
        args (namedtuple): This parameter represents the dictionary
		    that will hold all the arguments passed in and retrieved from PMP
        """
    try: 
        logging.info("Cloning Git Repository: {0}".format(args.source_repository))

        repo_url = "https://github.com/{0}/{1}".format(args.source_library, args.source_repository)        

        git_ssh_identity_file = os.path.expanduser('~/.ssh/is_rsa').replace(os.sep,'/')
        git_ssh_cmd = 'ssh -i %s' % git_ssh_identity_file
        
        repo_dir = os.path.join(args.temp_dir,args.source_repository).replace(os.sep, '/')
        os.environ['GIT_SSH_COMMAND'] = git_ssh_cmd
        Repo.clone_from(repo_url, repo_dir, env=dict(GIT_SSH_COMMAND=git_ssh_cmd), branch=args.active_branch, depth=1)

    except Exception as exc:
        logging.info("Failure in clone_repository.  " + str(exc))
        sys.exit("Failure in clone_repository.")

def get_previous_version(args):
    """This method retrieves the previously stored GMS configuration for comparison
    Args:
        args (namedtuple): This parameter represents the dictionary
		    that will hold all the arguments passed in and retrieved from PMP
    """
    folder = "{0}/{1}/{2}".format(args.temp_dir,args.source_repository, args.source_folder).replace(os.sep, '/')

    audit_file = "{0}/{1}.json".format(folder, args.source_configuration_id)
    if os.path.isfile(audit_file):
        logging.info("Previous Version Exists For: {0}".format(audit_file))
        with open(audit_file, 'r', encoding='utf8') as file:
            previous_gms_config_data = json.load(file)
        return previous_gms_config_data

    logging.info("No Previous Version Exists For: {0}".format(audit_file))

    return None

def parse_config(gms_config_object, result_list, parent):
    """This method is called recursively when the underlining value
    is of type dict and ultimately flattens out the config to easily be compared.
    Args:
        gms_config_object (json): This parameter represents the gms configs
        result_list (list):  The flattened out results will be appended to this list.
        parent (str): The parent name
    """
    for key in gms_config_object.keys():
        if isinstance(gms_config_object[key], dict):
            parse_config(gms_config_object[key], result_list, key)
        else:
            result_list.append({"parent": parent, "key": key, "value": gms_config_object[key]})


def commit_and_push(args, current_gms_config):
    """This method adds the initial GMS configuration to the repo as well as changes
    Args:
        args (namedtuple): This parameter represents the dictionary
		    that will hold all the arguments passed in and retrieved from PMP
        current_gms_config (json): This parameter represents the current gms configs
    """

    folder = "{0}\\{1}\\{2}".format(args.temp_dir,args.source_repository, args.source_folder)

    if not os.path.exists(folder):
        os.mkdir(folder)

    filename = "{0}\\{1}.json".format(folder, args.source_configuration_id)
    with open(filename, encoding='utf-8', mode='w') as file:
        file.write(current_gms_config['configuration'])

    logging.info("Committing Updated Configuration File")    
    logging.info("Adding {0}.json".format(args.source_configuration_id))

    repo_url = folder = "{0}\\{1}".format(args.temp_dir,args.source_repository)
    git_ssh_identity_file = os.path.expanduser('~/.ssh/is_rsa').replace(os.sep,'/')
    git_ssh_cmd = 'ssh -i %s' % git_ssh_identity_file
    os.environ['GIT_SSH_COMMAND'] = git_ssh_cmd

    repo = Repo(repo_url)
    with repo.git.custom_environment(GIT_SSH_COMMAND=git_ssh_cmd):
        repo.remotes.origin.fetch()
        repo.index.add([filename])
        comment =  "Configuration Changed by {0} {1}".format(current_gms_config['user']['user']['first_name'], \
            current_gms_config['user']['user']['last_name'])
        repo.index.commit(comment)
        repo.remotes.origin.push()

def get_changes(current_gms_config, previous_gms_config):
    """This method returns a list of changes between the current and previous versions.
    Args:
        current_gms_config (json): This parameter represents the current gms configs
        previous_gms_config (json): This parameter represents the previous gms configs
    """

    logging.info("Searching for changes")

    current_list = []
    previous_list = []
    results = []

    if previous_gms_config:
        parse_config(current_gms_config, current_list, '')
        parse_config(previous_gms_config, previous_list, '')

        results = [item for item in current_list if item not in previous_list]

    return results

def send_mail(args, email_contents):
    """ This method sends an email
    """
    url = "https://func-mail-" + args.env + ".azurewebsites.net/api/send_mail"
    is_complete = False
    retry_count = 0
    max_retries = int(os.environ['MAX_RETRIES'])
    sleep_time = int(os.environ['SLEEP_TIME_IN_SECONDS'])

    try:
        while not is_complete:
            results = requests.post(url, \
            headers={'x-functions-key': args.func_mail, }, data=json.dumps(email_contents))
            status = results.status_code
            if status != 200:
                if retry_count < max_retries:
                    retry_count += 1
                    time.sleep(sleep_time)
                else:
                    raise Exception('ERROR - SendMail failed.')
            else:
                is_complete = True

    except:
        logging.info("Failure in send_email.  Reason: %s", results.reason)
        sys.exit("Failure in send_email.")

    return results.json()


def send_notification(args, change_list, current_config):
    """This method sends a notification when there are changes to the the GMS configuration. If
    there are no changes write to the log that there are no changes.
    Args:
        args (namedtuple): This parameter represents the dictionary
		    that will hold all the arguments passed in and retrieved from PMP
        change_list (list): This parameter represents the changes to the GMS changes configurations.
        current_config (json): This parameter represents the current gms configs
    """
    if change_list:
        logging.info("Sending Notification")
        first_name = current_config['user']['user']['first_name']
        last_name = current_config['user']['user']['last_name']
        email = current_config['user']['user']['email']

        subject = "GMS Configuration Change Notification"

        if args.env.upper() != 'PRD':
            subject = args.env.upper() + " - " + subject

        body = []

        body.append("<p>The following changes to the GMS configuration were found since the last run:</p>")
        for change in change_list:
            body.append("</br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{0} {1}".format(change["parent"], \
                change["key"]))
        body.append("</br></br>Updated At {0}".format(current_config['updated_at']))
        body.append("</br>Updated By {0} {1} ({2})".format(first_name, last_name, email))

        if not args.is_debug:
            recipient_list = args.notification_list
            test_header = ""
            test_text = ""
            cc_list = os.environ.get('EMAIL_CC_LIST', '').split(',')
        else:
            recipient_list = os.environ.get('EMAIL_TO_LIST_TEST', '').split(',')
            test_header = " ***TEST*** "
            test_text = "The following email is a test from the " + \
            args.env + " environment. <br><br>"
            cc_list = os.environ.get('EMAIL_CC_LIST_TEST', '').split(',')
        
        body.insert(0, test_text)
        body="".join(body)

        email_contents = {
            "recipient_list": recipient_list,
            "cc_list": cc_list,
            "bcc_list": [],
            "subject": test_header + subject + test_header,
            "body": body,
            "attachments": []
            }
        send_mail(args, email_contents)

        
    else:
        logging.info("No Changes Found - No Notification Sent")


#==============================================================
# Main Logic Flow
#==============================================================

def main(mytimer: func.TimerRequest) -> None:
    utc_timestamp = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc).isoformat()

    if mytimer.past_due:
        logging.info('The timer is past due!')

    logging.info('process-configurations-timer trigger function ran at %s', utc_timestamp)

    logging.info("*** Retrieving Parameters For Job")
    args = parse_arguments()   

    access_token = get_access_token(args)

    logging.info("*** Performing Cleanup")
    cleanup(args)
    
    logging.info("*** Getting GMS Configuration")
    current_gms_config = get_gms_config(args, access_token)

    logging.info("*** Cloning Repository")
    clone_repository(args)

    logging.info("*** Getting Previous GMS Configuration")
    previous_gms_config = get_previous_version(args)

    logging.info("*** Get Changes")
    change_list = get_changes(json.loads(current_gms_config['configuration']), previous_gms_config)

    logging.info("*** Send Notification")
    send_notification(args, change_list, current_gms_config)

    if change_list or not previous_gms_config:
        logging.info("*** Commit and Push Changed Configuration")
        commit_and_push(args, current_gms_config)

    logging.info("*** Performing Cleanup")
    cleanup(args)
    
    logging.info("success")    

    logging.info('process-configurations-timer successfully finished at %s', utc_timestamp)