#!/usr/bin/bash

# DB backup

export HM=/home/illiusrock

# Full backup
/opt/local/bin/pg_dumpall -U postgres -h localhost -c | gzip > $HM/backups/db_dump_`date "+%Y%m%d"`.gz

# DB backup
/opt/local/bin/pg_dump -U postgres -h localhost irock | gzip > $HM/backups/db_dump_irock_`date "+%Y%m%d"`.gz

ls $HM/backups/db_dump_*`date "+%Y%m"`*
echo ""
echo "DB exported"
