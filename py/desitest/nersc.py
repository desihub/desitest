"""
Tools for updating and testing code at NERSC
"""

from __future__ import absolute_import, division, print_function
import sys, os
import subprocess
import time

def update(basedir=None, logdir='.', repos=None):
    '''TODO: Document'''
    if basedir is None:
        ### basedir = '/global/common/{}/contrib/desi/code/'.format(os.getenv('NERSC_HOST'))
        ### basedir = '/global/common/{}/contrib/desi/desiconda/current/code/'.format(os.getenv('NERSC_HOST'))
        ### basedir = '/global/common/software/desi/{}/desiconda/current/code/'.format(os.getenv('NERSC_HOST'))
        basedir = os.path.normpath(os.getenv('DESICONDA') + '/../code')

    if not os.path.exists(basedir):
        raise ValueError("Missing directory {}".format(basedir))

    logdir = os.path.abspath(logdir)
    if not os.path.exists(logdir):
        raise ValueError("Missing log directory {}".format(logdir))

    results = dict()

    #- repositories to update in order of dependencies
    #- TODO: consider speclite, and redmonster or redrock
    if repos is None:
        repos = [
            'desiutil',
            'specter',
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
            'prospect',
            'desimeter',
        ]

    something_failed = False
    for repo in repos:
        t0 = time.time()
        repo_results = dict()
        repodir = os.path.join(basedir, repo, 'master')
        repo_results['updated'] = False
        if not os.path.exists(repodir):
            repo_results['status'] = 'FAILURE'
            repo_results['log'] = 'Missing directory {}'.format(repodir)
            repo_results['updated'] = False
        else:
            os.chdir(repodir)
            repo_results['log'] = ['--- {}'.format(repodir), '']
            commands = [
                "git pull",
                "python -m compileall -f ./py",
                "python setup.py test",
            ]
            
            #- special cases for commands

            #- fiberassign: compiled code
            if repo == 'fiberassign':
                ### commands = ['git pull', 'make install']
                commands = ['git pull', 'python setup.py build_ext --inplace']

            #- desimodel: also update svn data
            if repo == 'desimodel':
                commands = ['svn update data/',] + commands

            #- specsim: python code not under py/
            if repo == 'specsim':
                i = commands.index('python -m compileall -f ./py')
                commands[i] = 'python -m compileall -f specsim'

            #- desisim-testdata & redrock-templates: data only, no tests
            #- prospect: no unit tests
            if repo in ['desisim-testdata', 'redrock-templates', 'prospect']:
                commands = ['git pull', ]

            #- desisim: use desisim-testdata to run faster
            if repo == 'desisim':
                i = commands.index('python setup.py test')
                commands[i] = 'module load desisim-testdata && python setup.py test'

            #- simqso: no py/ subdir; no tests
            if repo == 'simqso':
                commands = [
                    "git pull",
                    "python -m compileall -f simqso",
                    ]

            assert "git pull" in commands
            for cmd in commands:
                x = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, universal_newlines=True)
                repo_results['log'].extend( ['--- '+cmd, x.stdout] )

                if cmd == "git pull":
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

    for repo in repos:
        logfile = os.path.join(logdir, repo+'.log')
        with open(logfile, 'w') as fx:
            fx.write(results[repo]['log'])

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

    if something_failed:
        print("Updates+tests failed at {}".format(time.asctime()))
    else:
        print("Updates+tests succeeded at {}".format(time.asctime()))

    for repo in repos:
        updated = 'updated' if results[repo]['updated'] else 'same'
        print("{:12s} {:8s} {}".format(repo, updated, results[repo]['status']))

    return results
