# It's nyantip!

## Getting started

### Install

```sh
pip install nyancoin
```

If you would like to make encrypted backups, then install via:

```sh
pip install nyancoin[gpg]
```

### Database

Create a new MySQL database instance and run included SQL file `database.sql`
to create necessary tables. Create a MySQL user and grant it all privileges on
the database.

```sh
echo "create database nyantip" | mysql && mysql nyantip < database.sql
```

### NyanCoin Daemons

Download nyancoin. Create a configuration file for it in
`~/.nyancoin/nyancoin.conf` specifying `rpcuser`, `rpcpassword`, `rpcport`, and
`server=1`, then start the daemon. It will take some time for the daemon to
download the blockchain, after which you should verify that it's accepting
commands, e.g., `nyancoin getinfo` and `nyancoin listaccounts`.

### Reddit Account

Create a dedicated Reddit account for your bot, and prepare an OAuth
script-type application as described here:
<https://github.com/reddit-archive/reddit/wiki/OAuth2-Quick-Start-Example#first-steps>

### Configuration Files

Copy the sample configuration file `nyantip-sample.yml` to
`~/.config/nyantip.conf`. Make any necessary edits.

### Run

```sh
nyantip
```

### Create Backup

```sh
nyantip backup
```

The backup will be saved in your current directory as
`backup_nyantip_YYYYmmDDHHMM.zip`, or with the added `.gpg` suffix if a value
for `backup_passphrase` was set in your config file.

## History

`nyantip` was originally a fork of mohland's
[dogetipbot](https://github.com/mohland/dogetipbot), which in turn is a fork of
vindimy's [ALTcointip](https://github.com/vindimy/altcointip).
