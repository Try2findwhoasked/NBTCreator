import importlib.util,json,tempfile,unittest,zipfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('archive',Path(__file__).resolve().parents[1]/'scripts/portable-archive.py')
archive=importlib.util.module_from_spec(spec);spec.loader.exec_module(archive)

class PortableContracts(unittest.TestCase):
    def make_app(self,folder):
        app=folder/'NBTCreator-win32-x64'
        for name in ['NBTCreator.exe','resources/app/runtime/python/python.exe','resources/app/runtime/browser/chrome.exe','resources/app/.agents/skills/minecraft-nbt-modeler/SKILL.md']:
            p=app/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(name.encode())
        return app
    def test_hidden_skill_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);app=self.make_app(folder);zip=folder/'app.zip'
            archive.pack(app,zip);archive.unpack(zip,folder/'unpacked')
            self.assertTrue((folder/'unpacked'/app.name/'resources/app/.agents/skills/minecraft-nbt-modeler/SKILL.md').is_file())
            with self.assertRaises(FileExistsError):archive.pack(app,zip)
            with zip.open('ab') as stream:stream.write(b'changed')
            with self.assertRaisesRegex(ValueError,'checksum'):archive.unpack(zip,folder/'bad')
    def test_private_assets_and_traversal_rejected(self):
        for name in ['nbt_models','api-settings.json','.env']:
            with tempfile.TemporaryDirectory() as temporary:
                folder=Path(temporary);app=self.make_app(folder);(app/name).write_text('private')
                with self.assertRaisesRegex(ValueError,'Private'):archive.pack(app,folder/'app.zip')
        for name in ['../outside','/absolute','C:/escape','folder\\escape']:
            with self.assertRaises(ValueError):archive.valid_name(name)

if __name__=='__main__':unittest.main()
