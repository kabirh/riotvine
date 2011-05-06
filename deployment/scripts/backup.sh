#!/bin/bash

# DB backup

export HM=/home/web

# Full PG backup
/usr/bin/pg_dumpall -U postgres -h db -c | gzip > $HM/backups/db_dump_riotvine_full_`date "+%Y%m%d"`.gz

# Delete older than 4 days
find $HM/backups/db*gz -mtime +4 -exec rm {} \;

ls -la $HM/backups/db_dump_*`date "+%Y%m"`*

echo ""
echo "DB exported"

#
# /bin/cp -a /mnt/media /home/web/backups/.
# echo ""
# echo "Media copied to backup volume"
#
