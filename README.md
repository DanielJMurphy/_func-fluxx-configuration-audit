# func-fluxx-configuration-audit
## Overview

This script checks to see if the global configuration for GMS was changed and if
a change is found an email with what changed is sent to the GMS admins

```
    Retrieve Parameters For Job
    Perform Cleanup (delete old clone of fluxx-audit)
    Retrieve Currrent GMS Configuration into json object
    Clone fluxx-audit Repository
    Load Previous GMS Configuration into json object
    Get Changes - FLatting both configs into lists of dictionary and find the unmatched records
    if changed
        Send Notification
    if changed or the first time run 
        Commit and Push Changed Configuration
    Perform Cleanup
```

## Job Configuration

###### Notification List:

    GMS Admins

###### Processing Instructions:

```json
{
   "contexts":[
      {
         "name":"fluxx-configuration-audit",
         "stages":[
            {
               "name":"fluxx_configuration_audit",
               "parallel":true
            }
         ],
         "items":[
            {
               "context_item_name":"fluxx-configuration-audit",
               "parameters":[
                  {
                     "key":"SOURCE_LIBRARY",
                     "value":"macfound"
                  },
                  {
                     "key":"SOURCE_REPOSITORY",
                     "value":"fluxx-audit"
                  },
                  {
                     "key":"SOURCE_FOLDER",
                     "value":"configuration_audit"
                  },
                  {
                     "key":"SOURCE_CONFIGURATION_ID",
                     "value":"47"
                  },
                  {
                     "key":"ACTIVE_BRANCH",
                     "value":"dev"
                  },
                  {
                     "key":"SLEEP_TIME_IN_SECONDS",
                     "value":"30"
                  },
                  {
                     "key":"MAX_RETRIES",
                     "value":"3"
                  },                  
                  {
                     "key":"GMS_PER_PAGE",
                     "value":"100"
                  },
                  {
                     "key":"EMAIL_CC_LIST",
                     "value":???
                  },
                  {
                     "key":"EMAIL_CC_LIST_TEST",
                     "value":???
                  },
                  {
                     "key":"EMAIL_TO_LIST_TEST",
                     "value":???
                  },
                  {
                     "key":"EMAIL_TO_LIST",
                     "value":???
                  },
                  {
                     "key":"EMAIL_CC_LIST",
                     "value":???
                  },
                  {
                     "key":"IS_DEBUG",
                     "value":"False"
                  },
                  {
                     "key":"ENVIRONMENT",
                     "value":"prd"
                  }
               ]
            }
         ]
      }
   ]
}
```

###### Execution Schedule:

    The job is runs hourly



