from pathlib import Path
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import compatibility as c


class FixtureSandboxTests(unittest.TestCase):
    def setUp(self):
        original=c.shutil.which
        self.which=patch.object(c.shutil,'which',side_effect=lambda name:sys.executable if name=='codex' else original(name))
        self.which.start();self.addCleanup(self.which.stop)
    def fixture(self, root):
        home=root/'home'
        home.mkdir()
        (home/'config.toml').write_text('model="current"\n')
        fixture=root/'fixture'
        fixture.mkdir()
        return home,fixture

    @unittest.skipUnless(os.name=='nt','Native MXC fixture adapter is Windows-only.')
    def test_explicit_readonly_profile_isolated_python_and_selected_home(self):
        with tempfile.TemporaryDirectory() as td:
            home,fixture=self.fixture(Path(td))
            def command(args,cwd,env,timeout):
                self.assertEqual(args[1:4],['sandbox','--permission-profile',':read-only'])
                self.assertIn('features.prefer_mxc=true',args)
                self.assertEqual(args[args.index('--')+2:args.index('--')+6],['-I','-S','-B','-c'])
                self.assertEqual(env['CODEX_HOME'],str(home))
                self.assertEqual(cwd,fixture)
                return {'exit_code':0,'stdout':args[-1]+'\n?? retained.txt\0','stderr':''}
            with patch.object(c,'_cmd',side_effect=command) as called:
                result=c._fixture_python(['-c','assert True'],fixture,home)
            self.assertEqual(called.call_count,1)
            self.assertEqual(result['stdout'],'?? retained.txt\0')
            self.assertTrue(result['sandbox']['global_config_write_denial_verified'])

    @unittest.skipUnless(os.name=='nt','Native MXC fixture adapter is Windows-only.')
    def test_native_failure_never_runs_an_unsandboxed_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            home,fixture=self.fixture(Path(td))
            with patch.object(c,'_cmd',return_value={'exit_code':1,'stdout':'','stderr':'MXC unavailable'}) as called:
                with self.assertRaisesRegex(RuntimeError,'no fallback'):
                    c._fixture_python(['-m','unittest'],fixture,home)
            self.assertEqual(called.call_count,1)

    @unittest.skipUnless(os.name=='nt','Native MXC fixture adapter is Windows-only.')
    def test_test_failure_remains_a_failure_after_verified_confinement(self):
        with tempfile.TemporaryDirectory() as td:
            home,fixture=self.fixture(Path(td))
            def command(args,*unused,**kwargs):
                return {'exit_code':1,'stdout':args[-1]+'\n','stderr':'FAILED (failures=1)'}
            with patch.object(c,'_cmd',side_effect=command):
                result=c._fixture_python(['-m','unittest'],fixture,home)
            self.assertEqual(result['exit_code'],1)
            self.assertEqual(result['stderr'],'FAILED (failures=1)')

    @unittest.skipUnless(os.name=='nt','Native MXC fixture adapter is Windows-only.')
    def test_git_validation_uses_the_same_guarded_runner(self):
        with tempfile.TemporaryDirectory() as td:
            home,fixture=self.fixture(Path(td))
            def command(args,*unused,**kwargs):
                invocation=json.loads(args[-2])
                self.assertEqual(invocation['kind'],'git')
                self.assertTrue(Path(invocation['executable']).is_absolute())
                self.assertEqual(invocation['arguments'],['--no-pager','-c','core.fsmonitor=false','status','--porcelain=v1','-z'])
                return {'exit_code':0,'stdout':args[-1]+'\n','stderr':''}
            with patch.object(c,'_cmd',side_effect=command):
                self.assertEqual(c._fixture_git(['status','--porcelain=v1','-z'],fixture,home)['exit_code'],0)

    def test_unconfined_bootstrap_stops_before_any_fixture_code(self):
        with tempfile.TemporaryDirectory() as td:
            home,fixture=self.fixture(Path(td))
            sentinel=fixture/'fixture-code-executed.txt'
            payload={'kind':'python','arguments':['-c',f'from pathlib import Path; Path({str(sentinel)!r}).write_text("unexpected")']}
            with socket.socket() as listener:
                listener.bind(('127.0.0.1',0))
                listener.listen(1)
                result=subprocess.run([sys.executable,'-I','-S','-B','-c',c._FIXTURE_BOOTSTRAP,
                    str(listener.getsockname()[1]),str(home/'config.toml'),str(fixture),json.dumps(payload),'GUARD_READY'],
                    cwd=fixture,capture_output=True,encoding='utf-8',timeout=10)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(sentinel.exists())
            self.assertNotIn('GUARD_READY',result.stdout)
            self.assertIn('fixture code was not run',result.stderr)

    def test_only_fixed_validation_invocations_are_accepted(self):
        with patch.object(c,'_cmd') as called:
            with self.assertRaises(ValueError):c._fixture_python(['-m','os'],Path('.'),Path('.'))
            with self.assertRaises(ValueError):c._fixture_git(['config','core.fsmonitor','unsafe'],Path('.'),Path('.'))
        called.assert_not_called()

    def test_existing_replay_api_resolves_home_from_verified_cache(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            fable=home/'plugins/cache/fable5/fable5-codex/1.3.2/.agents/skills/fable5-codex/SKILL.md'
            fable.parent.mkdir(parents=True)
            fable.write_text('example')
            self.assertEqual(c._fixture_home({'path':str(fable)},None),home.resolve())

    @unittest.skipIf(os.name=='nt','Exercises the unsupported-platform guard.')
    def test_other_platform_fails_before_native_execution(self):
        with patch.object(c,'_cmd') as called:
            with self.assertRaisesRegex(RuntimeError,'only on Windows'):
                c._fixture_python(['-c','pass'],Path('.'),Path('.'))
        called.assert_not_called()


if __name__=='__main__':
    unittest.main()
