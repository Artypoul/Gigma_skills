from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[2]
PROFILE=REPO/'codex-profile/fable-superpowers'
PWSH=shutil.which('pwsh')


@unittest.skipUnless(PWSH,'PowerShell is required for launcher integration tests')
class PortableProfileTests(unittest.TestCase):
    def invoke(self,script,*arguments):
        result=subprocess.run([PWSH,'-NoProfile','-NonInteractive','-File',str(script),*map(str,arguments)],
            capture_output=True,encoding='utf-8',errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def make_spy(self,root):
        scripts=root/'codex-profile/fable-superpowers/scripts'
        scripts.mkdir(parents=True)
        shutil.copy2(PROFILE/'scripts/Install-FableSuperpowers.ps1',scripts)
        (scripts/'bootstrap.py').write_text('import json,sys; print(json.dumps(sys.argv[1:]))',encoding='utf-8')
        return scripts

    def test_installer_whatif_preserves_destination_and_forwards_quoted_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);scripts=self.make_spy(root)
            home=root/"other user's profile";marketplace=root/'Gigma Skills'
            args=self.invoke(scripts/'Install-FableSuperpowers.ps1','-CodexHome',home,'-MarketplaceRoot',marketplace,'-WhatIf')
            self.assertEqual(args[:2],['plan','--home'])
            self.assertEqual(args[3],'--marketplace-root')
            self.assertEqual(len(args),5)
            self.assertEqual(Path(args[2]).resolve(),home.resolve())
            self.assertEqual(Path(args[4]).resolve(),marketplace.resolve())
            self.assertFalse(home.exists())

    def test_profile_workflow_routes_to_canonical_installer_without_legacy_rules(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.make_spy(root)
            profile=root/'codex-profile';profile.mkdir(exist_ok=True)
            shutil.copy2(REPO/'codex-profile/setup.ps1',profile)
            home=root/'isolated home'
            args=self.invoke(profile/'setup.ps1','-CodexHome',home,'-Workflow','FableSuperpowers','-WhatIf')
            self.assertEqual(args[:2],['plan','--home'])
            self.assertEqual(args[3],'--marketplace-root')
            self.assertEqual(len(args),5)
            self.assertEqual(Path(args[2]).resolve(),home.resolve())
            self.assertEqual(Path(args[4]).resolve(),root.resolve())
            self.assertFalse(home.exists())

    def test_update_launcher_passes_selected_codex_home(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            shutil.copy2(PROFILE/'scripts/updater/Update-Superpowers.ps1',root)
            (root/'update.py').write_text('import json,sys; print(json.dumps(sys.argv[1:]))',encoding='utf-8')
            home=root/'custom home'
            args=self.invoke(root/'Update-Superpowers.ps1','-Action','check','-CodexHome',home)
            self.assertEqual(args[:2],['check','--home'])
            self.assertEqual(len(args),3)
            self.assertEqual(Path(args[2]).resolve(),home.resolve())

    def test_profile_and_installer_forward_retry_without_running_install_during_whatif(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);scripts=self.make_spy(root)
            profile=root/'codex-profile';profile.mkdir(exist_ok=True)
            shutil.copy2(REPO/'codex-profile/setup.ps1',profile)
            home=root/'retry destination'
            for script,extra in [(scripts/'Install-FableSuperpowers.ps1',[]),
                                 (profile/'setup.ps1',['-Workflow','FableSuperpowers'])]:
                with self.subTest(script=script):
                    args=self.invoke(script,'-CodexHome',home,*extra,'-WhatIf','-Retry')
                    self.assertEqual(args[0],'plan')
                    self.assertIn('--retry',args)
                    self.assertEqual(args.count('--retry'),1)
                    self.assertFalse(home.exists())

    def test_update_launcher_forwards_explicit_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            shutil.copy2(PROFILE/'scripts/updater/Update-Superpowers.ps1',root)
            (root/'update.py').write_text('import json,sys; print(json.dumps(sys.argv[1:]))',encoding='utf-8')
            args=self.invoke(root/'Update-Superpowers.ps1','-Action','run','-Retry')
            self.assertEqual(args,['run','--retry'])


if __name__=='__main__':unittest.main()
