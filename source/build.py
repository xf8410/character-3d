#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 three.min.js 与参考图数据 URI 内联进模板，产出自包含 index.html"""
import pathlib

BASE = pathlib.Path('/root/.codebuddy/artifact/whalegirl')
tpl = (BASE / 'template.html').read_text(encoding='utf-8')
three = (BASE / 'three.min.js').read_text(encoding='utf-8')
three = three.replace('</script', '<\\/script')

data = {}
for line in (BASE / 'refdata.txt').read_text().splitlines():
    if '=' in line:
        k, v = line.split('=', 1)
        data[k] = v

html = tpl.replace('/*__THREE_JS__*/', three)
missing = []
for k, v in data.items():
    token = '__' + k + '__'
    if token in html:
        html = html.replace(token, v)
    else:
        missing.append(token)
leftover = [t for t in ['__REF_FRONT__', '__REF_SIDE__', '__REF_BACK__', '__REF_FRONT_PANEL__', '/*__THREE_JS__*/'] if t in html]
out = pathlib.Path('/workspace/character-3d/index.html')
out.write_text(html, encoding='utf-8')
print('written:', out, len(html), 'bytes')
print('missing tokens:', missing)
print('leftover tokens:', leftover)
