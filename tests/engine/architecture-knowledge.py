"""Retrieval operates on a bounded local book collection and preserves provenance."""

import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ENGINE = Path(__file__).resolve().parents[2]/'.agents/skills/minecraft-nbt-modeler/scripts'
sys.path.insert(0, str(ENGINE))
from nbt_architecture_knowledge import INDEX, build, search


class ArchitectureKnowledge(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.library = Path(folder.name)
        self.books = []
        self.add_book(101, 'gothic')
        self.add_book(102, 'renaissance')
        self.manifest = self.library/'books.json'
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(dict(schema_version=1, books=self.books)), encoding='utf-8')

    def add_book(self, identifier, style):
        file = f'pg{identifier}.txt'
        text = ('Metadata flying buttress\n*** START OF THE PROJECT GUTENBERG EBOOK FIXTURE ***\n'
                'CHAPTER I. BUTTRESSES\n\nA flying buttress carries lateral thrust away from the vault.\n'
                '*** END OF THE PROJECT GUTENBERG EBOOK FIXTURE ***\nLicense flying buttress\n')
        payload = text.encode('utf-8')
        (self.library/file).write_bytes(payload)
        self.books.append(dict(id=identifier, file=file, bytes=len(payload), styles=[style],
            sha256=hashlib.sha256(payload).hexdigest(), title=style, author='Fixture', source='fixture',
            edition='Fixture edition', region='Fixture region', source_type='fixture'))

    def test_chinese_alias_and_style_return_original_lines_without_front_matter(self):
        receipt = build(self.library)
        self.assertEqual(receipt['books'], 2)
        hit, = search(self.library, '飞扶壁', 'gothic')['hits']
        self.assertEqual(hit['book'], 101)
        self.assertEqual(hit['line_start'], 3)
        self.assertEqual(hit['heading'], 'CHAPTER I. BUTTRESSES')
        self.assertNotIn('Metadata', hit['text'])
        self.assertNotIn('License', hit['text'])
        self.assertEqual(hit['sha256'], self.books[0]['sha256'])

    def test_rejects_stale_manifest_changed_source_and_changed_passage(self):
        build(self.library)
        self.books[0]['title'] = 'New label'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'manifest changed'):
            search(self.library, 'flying buttress')
        build(self.library)
        file = self.library/'pg101.txt'
        original = file.read_bytes()
        file.write_bytes(original.replace(b'lateral', b'altered'))
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            search(self.library, 'flying buttress', 'gothic')
        file.write_bytes(original)
        with sqlite3.connect(self.library/INDEX) as db:
            db.execute("UPDATE passages SET text = text || ' flying buttress' WHERE book=101")
        db.close()
        with self.assertRaisesRegex(ValueError, 'passage differs'):
            search(self.library, 'flying buttress', 'gothic')


if __name__ == '__main__':
    unittest.main(verbosity=2)
