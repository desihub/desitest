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

    #- repositories to update in order of desimodules
    if repos is None:
        repos = [
            'desiutil',
            'specter',
            'gpu_specter',
            'desimodel',
            'specex',
            'desitarget',
            'specsim',
            'desispec',
            'desisim-testdata',
            'desisim',
            'fiberassign',
            'desisurvey',
            'surveysim',
            'redrock',
            'redrock-templates',
            'prospect',
            'desimeter',
            'simqso',
            'speclite',
            'QuasarNP',
            'specprod-db',
            'fastspecfit',
            'desisurveyops',  # not included in desimodules
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
            print(f'WARNING: using {repo}/master instead of main')

        #- special cases for testing
        pytestcom = "pytest py/"+repo+"/test"
        if repo == 'specsim':
            pytestcom = "pytest "+repo+"/tests"
        elif repo == 'desisim':
            #- use desisim-testdata for faster testing
            pytestcom = ('module load desisim-testdata && '+pytestcom
                                   +' && '+'module unload desisim-testdata')

        if not os.path.exists(repodir):
            repo_results['status'] = 'FAILURE'
            repo_results['log'] = 'Missing directory {}'.format(repodir)
            repo_results['updated'] = False
        else:
            os.chdir(repodir)
            repo_results['log'] = ['--- {}'.format(repodir), '']
            commands = [
                pullcmd,
                "python -m compileall -f ./py",
                pytestcom,
            ]

            #- special cases for commands

            #- fiberassign: compiled code
            if repo == 'fiberassign':
                commands = [pullcmd, 'python setup.py build_ext --inplace', pytestcom]

            #- specex: compiled code
            if repo == 'specex':
                commands = [pullcmd, 'python setup.py build_ext --inplace', pytestcom]

            #- desimodel: also update svn data
            if repo == 'desimodel':
                commands = ['svn update data/',] + commands

            #- specsim: python code not under py/
            if repo == 'specsim':
                i = commands.index('python -m compileall -f ./py')
                commands[i] = 'python -m compileall -f specsim'

            #- desisim-testdata & redrock-templates: data only, no tests
            if repo in ['desisim-testdata', 'redrock-templates']:
                commands = [pullcmd, ]

            #- prospect, desisurveyops, LSS: no unit tests
            if repo in ['prospect', 'desisurveyops', 'LSS']:
                commands = [
                    pullcmd,
                    "python -m compileall -f ./py",
                    ]

            #- simqso: no py/ subdir; no tests
            if repo == 'simqso':
                commands = [
                    pullcmd,
                    "python -m compileall -f simqso",
                    ]

            # always set permissions as the last command
            commands.append(chmodcmd)

            assert pullcmd in commands

            if testonly:
                if repo in ('simqso', 'prospect', 'desisurveyops', 'desisim-testdata', 'redrock-templates'):
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
    with open(os.path.join(logdir, 'index.html'), 'w') as fx:
        fx.write('<html>\n<body>\n')
        fx.write('<h1>Updated {}</h1>\n'.format(time.asctime()))
        fx.write('<table>\n')
        fx.write('  <tr>\n')
        fx.write('    <th>Repo</th><th>Updated</th><th>Status</th><th>Time</th>\n')
        fx.write('  </tr>\n')
        for repo in repos:
            fx.write('  <tr>\n')
            fx.write('    <td>{}</td>\n'.format(repo))
            if results[repo]['updated']:
                fx.write('    <td>yes</td>\n')
            else:
                fx.write('    <td></td>\n')

            fx.write('    <td><a href="{}.log">{}</a></td>\n'.format(repo, results[repo]['status']))
            dt = int(results[repo]['time'])
            timestr = '{:02d}:{:02d}'.format(dt//60, dt%60)
            fx.write('    <td>{}</td>\n'.format(timestr))
            fx.write('  </tr>\n')
        fx.write('</table>\n</body>\n</html>\n')

    for repo in repos:
        updated = 'updated' if results[repo]['updated'] else 'same'
        print("{:12s} {:8s} {}".format(repo, updated, results[repo]['status']))

    print(startup_permissions_msg)

    if something_failed:
        print("\nSome updates+tests failed {}".format(time.asctime()))
    else:
        print("\nAll updates+tests succeded {}".format(time.asctime()))

    print("\nhttp://data.desi.lbl.gov/desi/spectro/redux/dailytest/log/"+os.environ['NERSC_HOST'])
    sys.stdout = stdout

    emailfile=os.path.dirname(os.path.abspath(__file__))+'/emails.txt'
    if os.path.isfile(emailfile):
        emails=[line for line in open(emailfile,'r')][0].strip().split(',')
        to=emails[0]
        cc=emails[1:]
        send_email("perlmutter desitest",to,"perlmutter desitest {}".format(time.asctime()),output.getvalue(),Cc=cc)

    print(output.getvalue())

    return results
