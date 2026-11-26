## Productivity Next

Productivity Next

### Meeting sync

Open **Meeting Sync Settings** to enable Microsoft Teams or Google Meet. The form
includes provider setup guides. For Google Meet, use **Test Google Connection**
to check access to Meet, Calendar and Directory, then use **Sync Google Meet Now**
to run a poll.

Each completed call is stored in **Meeting Call Log**. Eligible calls get a draft
**Meeting** linked to the log. Transcripts are fetched separately, and **Send MOM**
opens an email draft using the saved Discussion.

#### Move an existing Meeting Sync site

Take a site backup and pause the scheduler while moving the integration. Use the
following commands to detach the standalone app and load the Productivity Next
DocType definitions. Detaching preserves the existing settings and call logs.

```sh
bench --site <site> remove-from-installed-apps meeting_sync
bench --site <site> migrate
```

Restart the processes that load app hooks, then resume the scheduler. If Teams is
enabled, use **Renew Teams Subscriptions** to register the new webhook URLs.

#### License

GPL 3.0
