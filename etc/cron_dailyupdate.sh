#!/bin/bash
#PBS -q debug
#PBS -l walltime=00:30:00
#PBS -l mppwidth=24
#PBS -A desi
#PBS -j oe

#- Cron/batch job to run daily integration tests on edison.nersc.gov
### 0 1 * * * /bin/bash -lc "source /global/common/software/desi/users/desi/desitest/etc/cron_dailyupdate.sh"

#- Figure out where we are before modules changes ${BASH_SOURCE[0]} (!)
SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYDIR=$SCRIPTDIR/../py

### set -e
echo `date` Running dailyupdate on `hostname`

#- Configure desi environment if needed
if [ -z "$DESI_ROOT" ]; then
    # module use /global/common/$NERSC_HOST/contrib/desi/modulefiles
    # module use /global/common/$NERSC_HOST/contrib/desi/desiconda/startup/modulefiles
    module use /global/common/software/desi/$NERSC_HOST/desiconda/startup/modulefiles
    module load desimodules/current
fi

#- Check if subversion needs to be loaded
#- Update 2018-04-12: no longer needed, but leaving code in case we need to
#- re-implement this logic later for another svn update.
# if [[ $(which svn) == "/usr/common/software/bin/svn" || $(which svn) == "/usr/bin/svn" ]]; then
#     module load subversion/1.9.4
# fi
# echo Using svn $(which svn)

#--------------------------------------------------------------------
#- Update from git and run unit tests
cd $PYDIR
logdir=/global/cfs/cdirs/desi/spectro/redux/dailytest/log/$NERSC_HOST
python -c "from desitest.nersc import update; update(logdir='$logdir')"

echo http://data.desi.lbl.gov/desi/spectro/redux/dailytest/log/$NERSC_HOST
echo

#--------------------------------------------------------------------
#- Run integration test

#- Ensure that $SCRATCH is defined so that we don't accidentally clobber stuff
#- cronjob environment doesn't set SCRATCH
if [ -z "$SCRATCH" ]; then
    export SCRATCH=/scratch1/scratchdirs/desi
    echo "WARNING: setting \$SCRATCH=$SCRATCH"
fi

#- Where should output go?
export DAILYTEST_ROOT=$SCRATCH/dailytest

export PIXPROD=dailytest
export DESI_SPECTRO_DATA=$DAILYTEST_ROOT/spectro/sim/$PIXPROD
export DESI_SPECTRO_SIM=$DAILYTEST_ROOT/spectro/sim

export PRODNAME=dailytest
export SPECPROD=dailytest
export DESI_SPECTRO_REDUX=$DAILYTEST_ROOT/spectro/redux

#- Cleanup from previous tests
simdir=$DESI_SPECTRO_SIM/$PIXPROD
outdir=$DESI_SPECTRO_REDUX/$PRODNAME
rm -rf $simdir
rm -rf $outdir

#- Run the integration test
mkdir -p $simdir
mkdir -p $outdir
# python -m desispec.test.integration_test > $outdir/dailytest.log
python -m desispec.test.old_integration_test > $outdir/dailytest.log

echo
echo "[...]"
echo

tail -10 $outdir/dailytest.log

echo `date` done with dailytest
