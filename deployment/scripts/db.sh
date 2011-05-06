#!/bin/bash

/usr/bin/psql -U postgres -h db rvine -c "VACUUM VERBOSE ANALYZE event_eventtweet"
