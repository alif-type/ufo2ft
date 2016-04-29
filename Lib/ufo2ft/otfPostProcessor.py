from __future__ import print_function, division, absolute_import, unicode_literals

import tempfile

from compreffor import Compreffor
from fontTools.ttLib import TTFont


class OTFPostProcessor(object):
    """Does some post-processing operations on a compiled OpenType font, using
    info from the source UFO where necessary.
    """

    def __init__(self, otf, ufo):
        self.ufo = ufo
        tmp_file = tempfile.NamedTemporaryFile()
        tmp_path = tmp_file.name
        otf.save(tmp_path)
        self.otf = TTFont(tmp_path)

    def process(self, useProductionNames=True, optimizeCff=True):
        if useProductionNames:
            self._rename_glyphs_from_ufo()
        if optimizeCff and 'CFF ' in self.otf:
            comp = Compreffor(self.otf)
            comp.compress()
        return self.otf

    def _rename_glyphs_from_ufo(self):
        """Rename glyphs using glif.lib.public.postscriptNames in UFO."""

        rename_map = {
            g.name: self._build_production_name(g) for g in self.ufo}
        rename = lambda names: [rename_map[n] for n in names]

        self.otf.setGlyphOrder(rename(self.otf.getGlyphOrder()))
        if 'CFF ' in self.otf:
            cff = self.otf['CFF '].cff.topDictIndex[0]
            char_strings = cff.CharStrings.charStrings
            cff.CharStrings.charStrings = {
                rename_map.get(n, n): v for n, v in char_strings.items()}
            cff.charset = rename(cff.charset)

    def _build_production_name(self, glyph):
        """Build a production name for a single glyph."""

        # use name from Glyphs source if available
        production_name = glyph.lib.get('public.postscriptName')
        if production_name:
            return production_name

        # use name derived from unicode value
        unicode_val = glyph.unicode
        if glyph.unicode is not None:
            return '%s%04X' % (
                'u' if unicode_val > 0xffff else 'uni', unicode_val)

        # use production name + last (non-script) suffix if possible
        parts = glyph.name.rsplit('.', 1)
        if len(parts) == 2 and parts[0] in self.ufo:
            return '%s.%s' % (
                self._build_production_name(self.ufo[parts[0]]), parts[1])

        # use ligature name, making sure to look up components with suffixes
        parts = glyph.name.split('.', 1)
        if len(parts) == 2:
            liga_parts = ['%s.%s' % (n, parts[1]) for n in parts[0].split('_')]
        else:
            liga_parts = glyph.name.split('_')
        if len(liga_parts) > 1 and all(n in self.ufo for n in liga_parts):
            unicode_vals = [self.ufo[n].unicode for n in liga_parts]
            if all(v and v <= 0xffff for v in unicode_vals):
                return 'uni' + ''.join('%04X' % v for v in unicode_vals)
            return '_'.join(
                self._build_production_name(self.ufo[n]) for n in liga_parts)

        return glyph.name
