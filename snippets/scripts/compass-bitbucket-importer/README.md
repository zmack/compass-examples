## Bootstrap your Compass Catalog with from a Bitbucket Data Center Instance

This script
1. Iterates over all your Bitbucket projects and all the repos within them
2. Creates Compass Components for each of them
3. Connects your Bitbucket repo by adding a Compass repository link to the created component


## Install

You'll need node and npm to run this script

```
git clone https://github.com/atlassian-labs/compass-examples
cd snippets/scripts/compass-bitbucket-importer
npm install
```

## Credentials
Create a `.env` file and fill in the blanks. This file should be ignored by git already since it is in the `.gitignore`
```
# Replace these with your GitHub instance URL and access token (ex. 'bitbucket.test.com')
BITBUCKET_URL='<your bitbucket>'
#A Base64 encoded version of the following string `username:password`
ACCESS_TOKEN='<encoded string>'
USER_EMAIL='<atlassian email>'
# https://id.atlassian.com/manage-profile/security/api-tokens
TOKEN='<atlassian token>'
# Add your subdomain here - find it from the url - e.g. https://<southwest>.atlassian.net
TENANT_SUBDOMAIN='<subdomain>'
# The UUID for your cloud site. This can be found in ARIs - look at the first uuid ari:cloud:compass:{cloud-uuid}
CLOUD_ID='<cloud uuid>'
```
## Do a dry run
Preview what Repos the script will add to Compass. You don't need to wait until it's done - CTRL-C once you are comfortable.
```
DRY_RUN=1 node index.js
```

Output:
```
New component for https://bitbucket.com/hyde.me/test_gb_less3_2 ... would be added hyde.me/test_gb_less3_2 (dry-run)
New component for https://bitbucket.com/sachintomar009/reposetup ... would be added sachintomar009/reposetup (dry-run)
New component for https://bitbucket.com/brianwilliamaldous/api-la ... would be added brianwilliamaldous/api-la (dry-run)
New component for https://bitbucket.com/cloud-group3072118/timely ... would be added cloud-group3072118/timely (dry-run)
....

```


By default, all repos will be added. If you notice any repositories that you don't want to import during the dry run, you can modify `index.js` to add filters accordingly.

```javascript
for (const repo of repos) {
    // need a filter, add one here!
    /*
    Example, skip is repo name is "hello-world"
    if (repo.name !== 'hello-world')
     */
    if (true) {
        await putComponent(repo.name, repo.description || '', `https://${BITBUCKET_URL}/projects/${project.key}/repos/${repo.slug}`)
    }
}
```

## Ready to import?
Remove `DRY_RUN=1` to run the CLI in write mode.
```
node index.js
```

If your connection is interrupted, or you want to re-run after the initial import you can. It checks for duplicates and skips them:

```
Already added https://bitbucket.com/VishnuprakashJ/home ... skipping
```

## Next steps

Once you're finished set up the on-prem webhook to link deployments, builds, etc to Compass. You only have to do this once (not once per Component) and Compass will associate the repo events with the Component they interact with.

https://developer.atlassian.com/cloud/compass/components/create-incoming-webhooks/