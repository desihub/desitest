# desitest

This repo contains utilities for cross package testing of DESI code.

`etc/cron_dailyupdate.sh` is run as a cronjob on edison01.nersc.gov;
it calls `desitest.nersc.update()` to `git pull` the master copy of each repo
and run their unit tests, and then it runs the spectro pipeline integration
test (currently in desispec).

`bin/speedtest` has timing tests of several of our more CPU intensive codes.

In the future, integration tests for the spectro pipeline, quicklook, and
other end-to-end tests could be moved into this repo.
