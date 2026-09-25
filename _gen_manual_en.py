# -*- coding: utf-8 -*-
r"""FILTER - User Guide (EN). Generator on the family template (_docstyle.py).
Run:  python _gen_manual_en.py    Output:  docs\FILTER_Manual_EN.docx
"""

import json

import _docstyle as ds

OUT = r'D:\AI\ZCode\Project\FILTER\docs\FILTER_Manual_EN.docx'


def h1(doc, text):
    return ds.h1(doc, text)


def h2(doc, text):
    return ds.h2(doc, text)


def p(doc, text, bullet=False, italic=False, grey=False):
    return ds.p(doc, text, bullet=bullet, italic=italic, grey=grey)


def kv_note(doc, text):
    return ds.kv(doc, text)


def add_table(doc, rows, widths, sev_col=None):
    return ds.add_table(doc, rows, widths, sev_col=sev_col)


def _save(doc, out):
    ds.footer(doc.sections[1], 'FILTER')
    ds.strip_tail(doc)
    doc.save(out)
    h1s = [t for t in ds.H1_REGISTRY if t.lower() not in ('table of contents', 'contents')]
    json.dump(h1s, open(out.replace('.docx', '.h1.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    print('saved:', out)


doc = ds.new_doc('FILTER', 'User Guide', 'V1.4.1  -  BLENDER 4.2+')

p(doc, 'FILTER is a Blender extension for fast visibility control and modifier management. '
       'The panel lays the scene out by object type, collection and name: any type can be '
       'hidden, excluded from render or locked against selection in one click. A separate '
       'By Modifier block manages modifiers in bulk - find every Bevel in the scene, select '
       'the objects carrying them, apply or remove - with safe bake ordering and a mismatch '
       'detector.')

kv_note(doc, 'github.com/abyrvalg379/FILTER')

h1(doc, 'Contents')
ds.toc_field(doc, 'Table of contents: open the document in Word/LibreOffice and refresh '
                  'the field (F9) to fill in page numbers.')

h1(doc, '1. About FILTER')
p(doc, 'Key features:', bullet=False)
for b in (
    'visibility, selection and locking by object type: Mesh, Armature, Empty, Light, Camera;',
    'solo eye: show only the selected type or collection, hide everything else;',
    'render eye: exclude a type or collection from render without touching the viewport;',
    'name pattern filter (case-insensitive) and collection filter;',
    'By Modifier: bulk apply, remove and select across modifier groups;',
    'settings mismatch detector inside a modifier group;',
    'order-safe apply: stack order is preserved, baking runs only when required;',
    'linked-library objects are skipped, linked duplicates handled cleanly.',
):
    p(doc, b, bullet=True)

h1(doc, '2. Installation')
for b in (
    'Blender 4.2+: download filter.zip from the latest release github.com/abyrvalg379/FILTER - '
    'Preferences - Get Extensions - Install from Disk - pick the zip.',
    'Blender 3.0-4.1: same zip, via Preferences - Add-ons - Install.',
    'The panel appears in the 3D viewport N-panel (N key) - FILTER tab.',
):
    p(doc, b, bullet=True)

h1(doc, '3. Quick start')
p(doc, 'Two typical passes:')
for b in (
    'Clean viewport: in the By Type block press the solo eye (Shift + click) on the Mesh row - '
    'only geometry remains; armatures, empties and lights hide away. Another Shift + click '
    'restores everything.',
    'Bulk apply: By Modifier block - pick a group (e.g. Bevel) - Apply. If the modifier is not '
    'first in the stack, FILTER offers to bake the modifiers above it - the result on every '
    'object matches the viewport exactly.',
):
    p(doc, b, bullet=True)

h1(doc, '4. By Type')
p(doc, 'The block lays objects out by five types. Each type has its own buttons:')
add_table(doc, [
    ('Button', 'Action'),
    ('Toggle (eye)', 'hide/show every object of the type in the viewport'),
    ('Select', 'select all objects of the type'),
    ('Render (camera)', 'exclude/return the type in render, viewport untouched'),
    ('Lock', 'lock/unlock selection for the type'),
    ('Solo (Shift + click the eye)', 'show only this type, hide the rest; press again to restore'),
], [5.2, 11.8])
p(doc, 'The states do not conflict: you can keep lights hidden in the viewport yet rendering - '
       'the render eye and the viewport eye are independent.')

h1(doc, '5. By Name and Collections')
h2(doc, '5.1 By Name')
p(doc, 'Type a name pattern (case-insensitive) - Toggle hides or shows the matches, Select '
       'selects them. Handy for serial suffixes: _geo, _low, LOD*.')
h2(doc, '5.2 Collections')
p(doc, 'The block lists scene collections with the same visibility, selection and render '
       'buttons. Collection visibility runs through the outliner channels - what FILTER hides '
       'is honestly hidden in the outliner too, and the other way around.')

h1(doc, '6. By Modifier')
p(doc, 'The block gathers scene modifiers grouped by exact name or by type (group switch). '
       'The Scene / Selected scope limits the search: the whole scene or selected objects only.')
h2(doc, '6.1 Operations')
add_table(doc, [
    ('Operation', 'What it does'),
    ('Select', 'select every object carrying a modifier of the group'),
    ('Apply', 'apply the group modifier on all matched objects with order-safe semantics'),
    ('Remove', 'remove the group modifier from all matched objects'),
    ('Remove disabled', 'one click removes every viewport-disabled modifier in scope'),
    ('Select different', 'find and select objects whose group modifier has different settings'),
], [4.4, 12.6])
h2(doc, '6.2 Order-safe apply')
p(doc, 'If the applied modifier is not first in the stack, the result depends on what sits '
       'above it. FILTER resolves this correctly: modifiers above the target are baked top-down '
       'first, and only then the target is applied - the result on each object matches the '
       'viewport exactly. A confirmation dialog appears only when baking is actually required.')
h2(doc, '6.3 Special cases')
for b in (
    'linked duplicates (Alt+D) sharing a mesh datablock are made single-user automatically '
    'before apply;',
    'linked-library objects are skipped - foreign data is never modified;',
    'the mismatch detector: a line like "3 with different settings" means some modifiers of '
    'the group differ in parameters - Select different marks them for review.',
):
    p(doc, b, bullet=True)

h1(doc, '7. Workflows')
for t in (
    ('Clean model screenshot',
     'Solo eye on Mesh - armatures, empties and service objects vanish. Took the shot - '
     'Shift + click brings the scene back.'),
    ('Deliver a modifier-free model',
     'By Modifier - the Bevel group (or all by type) - Apply with bake confirmation. Run the '
     'mismatch detector to make sure nothing drifted, and Remove disabled just in case.'),
    ('Render without armatures and empties',
     'Render eye on Armature and Empty: the viewport stays as is, but the frame is clean.'),
    ('Reading a foreign scene',
     'Lock the types you must not touch (Armature), filter by the _geo name - and you work '
     'only with what you need.'),
):
    h2(doc, t[0])
    p(doc, t[1])

h1(doc, '8. Troubleshooting')
add_table(doc, [
    ('Symptom', 'Cause', 'What to do'),
    ('Apply shows a dialog', 'the modifier is not first in the stack - the ones above must be baked',
     'confirm: the result stays exactly as in the viewport; skipping the bake breaks the order'),
    ('Some objects were skipped on apply', 'linked-library objects or multi-user data',
     'linked duplicates become single-user automatically; linked objects are edited in their own library'),
    ('Collection visibility "does not apply"', 'the collection channel is off in the outliner',
     'it is a single state: check the collection eye in the outliner - FILTER and the outliner are in sync'),
    ('The name filter finds nothing', 'case or stray characters in the pattern',
     'the filter is case-insensitive; check the pattern (wildcards like * are supported)'),
    ('Object hidden but visible on render', 'the viewport eye and the render eye are independent states',
     'to exclude from render use the render eye (camera icon)'),
], [4.8, 5.4, 6.8])

_save(doc, OUT)
