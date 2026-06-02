"""
Tools for updating and testing code at NERSC
"""

import sys, os
import subprocess
import time
from io import StringIO
from desitest.util import send_email

def update(basedir=None, logdir='.', repos=None, testonly=False):
    '''Update git repos in basedir and run unit tests

    Args:
        basedir: base directory with git clones in packagename/[main|master]

    Options:
        logdir: output log directory
        repos: list of repos to update and test
        testonly (bool): if True, skip "git pull" and only run tests

    Writes logfiles from each git pull + tests plus index.html into logdir
    '''

    # store stdout in string
    stdout = sys.stdout
    sys.stdout = output = StringIO()

    print("Updates+tests started {}\n".format(time.asctime()))

    if basedir is None:
        basedir = os.path.normpath(os.getenv('DESICONDA') + '/../code')

    if not os.path.exists(basedir):
        raise ValueError("Missing directory {}".format(basedir))

    logdir = os.path.abspath(logdir)
    if not os.path.exists(logdir):
        raise ValueError("Missing log directory {}".format(logdir))

    results = dict()

    #- repositories to update in order of dependencies
    if repos is None:
        repos = [
            'desiutil',
            'specter',
            'gpu_specter',
            'speclite',
            'desimodel',
            'desitarget',
            'desispec',
            'specsim',
            'desisim-testdata',
            'desisim',
            'desisurvey',
            'surveysim',
            'redrock',
            'redrock-templates',
            'simqso',
            'fiberassign',
            'specex',
            'prospect',
            'desimeter',
            'desisurveyops',  # not included in desimodules
            'QuasarNP',
            'specprod-db',
            'fastspecfit',
            'desidatamodel',  # not included in desimodules
            'LSS',  # not included in desimodules
        ]

    pullcmd='git pull'
    chmodcmd='chmod -R a+rX .'

    something_failed = False

    for repo in repos:
        t0 = time.time()
        repo_results = dict()
        repo_results['updated'] = False

        repodir = os.path.join(basedir, repo, 'main')
        if not os.path.exists(repodir):
            repodir = os.path.join(basedir, repo, 'master')
            print(f'WARNING: trying to use {repo}/master instead of main')
            if not os.path.exists(repodir):
                print(f'ERROR: no checkout could be found for {repo}')
                repo_results['status'] = 'MISSING'
                repo_results['log'] = 'Missing directory {}'.format(repodir)
                repo_results['updated'] = False
                continue
        else:
            os.chdir(repodir)
            repo_results['log'] = ['--- {}'.format(repodir), '']
            #
            # Special cases for pulling
            #
            commands = [pullcmd]

            #- desimodel: also update svn data
            if repo == 'desimodel':
                commands = ['svn update data/', pullcmd]

            #
            # Special cases for building
            #
            buildcmd = "python -m compileall -f ./py"

            #- fiberassign, specex: compiled code
            if repo == 'fiberassign' or repo == 'specex':
                buildcmd = 'python setup.py build_ext --inplace'

            #- specsim, etc.: python code not under py/
            if repo == 'speclite' or repo == 'specsim' or repo == 'simqso':
                buildcmd = f"python -m compileall -f {repo}"

            #- desisim-testdata & redrock-templates: data only, no tests
            if repo == 'desisim-testdata' or repo == 'redrock-templates':
                buildcmd = None

            if buildcmd is not None:
                commands.append(buildcmd)
            #
            # Special cases for testing
            #
            pytestcom = f"pytest py/{repo}/test"

            if repo == 'specsim' or repo == 'speclite':
                pytestcom = f"pytest {repo}/tests"

            if repo == 'specprod-db':
                pytestcom = "pytest py/specprodDB/test"

            if repo == 'QuasarNP':
                pytestcom = "pytest quasarnp/tests"

            #- use desisim-testdata for faster testing
            if repo == 'desisim':
                pytestcom = ('module load desisim-testdata && ' + pytestcom +
                             ' && module unload desisim-testdata')

            #- desisurveyops, LSS, simqso: no unit tests
            if repo == 'desisurveyops' or repo == 'LSS' or repo == 'simqso':
                pytestcom = None

            #- desisim-testdata & redrock-templates: data only, no tests
            if repo == 'desisim-testdata' or repo == 'redrock-templates':
                pytestcom = None

            if pytestcom is not None:
                commands.append(pytestcom)

            # always set permissions as the last command
            commands.append(chmodcmd)

            assert pullcmd in commands

            if testonly:
                if pytestcom is None:
                    commands = [f'echo test only: skipping update of {repo}',]
                else:
                    commands = [pytestcom,]

            for cmd in commands:
                x = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, universal_newlines=True)
                repo_results['log'].extend( ['--- '+cmd, x.stdout] )

                if cmd == pullcmd:
                    if "Already up to date." in x.stdout:
                        repo_results['updated'] = False
                    else:
                        repo_results['updated'] = True

                if x.returncode != 0:
                    repo_results['status'] = 'FAIL'
                    something_failed = True
                    break
                else:
                    repo_results['status'] = 'ok'

        repo_results['time'] = time.time() - t0
        repo_results['log'] = '\n'.join(repo_results['log'])
        results[repo] = repo_results
        ### print('{:20s}  {}'.format(repo, results[repo]['status']))

#    uncomment next line to wait until end to write repo log files
#    for repo in repos:
        logfile = os.path.join(logdir, repo+'.log')
        with open(logfile, 'w') as fx:
            fx.write(results[repo]['log'])

    #- Also ensure world read to the startup module files
    #- Hardcode path, but at least confirm that it exists
    if not testonly:
        startupdir = os.path.expandvars('/global/common/software/desi/$NERSC_HOST/desiconda/startup')
        if os.path.exists(startupdir):
            os.chdir(startupdir)
            x = subprocess.run(chmodcmd, shell=True, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, universal_newlines=True)
            if x.returncode != 0:
                startup_permissions_msg = f'ERROR updating permissions of {startupdir}'
                something_failed = True
            else:
                startup_permissions_msg = f'Updated world read permissions for {startupdir}'
        else:
            something_failed = True
            startup_permissions_msg = f"ERROR: {startupdir} doesn't exist"

    #- Write index.html in log directory
    title = "desitest.nersc: Updated {0}".format(time.asctime())
    with open(os.path.join(logdir, 'index.html'), 'w') as fx:
        fx.write('<!DOCTYPE html>\n')
        fx.write(f'<html lang="en-US">\n<head><title>{title}</title></head>\n<body>\n')
        fx.write(f'<h1>{title}</h1>\n')
        fx.write('<table>\n')
        fx.write('  <thead>\n')
        fx.write('      <tr><th>Repo</th><th>Updated</th><th>Status</th><th>Time</th></tr>\n')
        fx.write('  </thead>\n')
        fx.write('  <tbody>\n')
        for repo in repos:
            up = 'yes' if results[repo]['updated'] else ''
            dt = int(results[repo]['time'])
            timestr = '{:02d}:{:02d}'.format(dt//60, dt%60)
            fx.write(f'    <tr><td>{repo}</td><td>{up}</td><td><a href="{repo}.log">{results[repo]["status"]}</a></td><td>{timestr}</td></tr>\n')
        fx.write('  </tbody>\n</table>\n</body>\n</html>\n')

    for repo in repos:
        updated = 'updated' if results[repo]['updated'] else 'same'
        print("{:12s} {:8s} {}".format(repo, updated, results[repo]['status']))

    print(startup_permissions_msg)

    if something_failed:
        print("\nSome updates+tests failed {}".format(time.asctime()))
    else:
        print("\nAll updates+tests succeded {}".format(time.asctime()))

    print("\nhttp://data.desi.lbl.gov/desi/spectro/redux/dailytest/log/"+os.environ['NERSC_HOST'])

    emailfile=os.path.dirname(os.path.abspath(__file__))+'/emails.txt'
    if os.path.isfile(emailfile):
        emails=[line for line in open(emailfile,'r')][0].strip().split(',')
        to=emails[0]
        cc=emails[1:]
        send_email("perlmutter desitest",to,"perlmutter desitest {}".format(time.asctime()),output.getvalue(),Cc=cc)
    else:
        print(f"WARNING: {emailfile} not detected so no email sent!")

    sys.stdout = stdout

    print(output.getvalue())

    return results
