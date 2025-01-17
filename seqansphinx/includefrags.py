'''
'''

import codecs
import os.path
import urllib.request, urllib.parse, urllib.error

from docutils import nodes, utils
from docutils.parsers.rst import Directive, directives

from sphinx import addnodes
from sphinx.util import parselinenos
from sphinx.util.nodes import set_source_info
from docutils.parsers.rst import Directive, directives

class IncludeFrags(Directive):
    """
    Like ``.. include:: :literal:``, but only warns if the include file is
    not found, and does not raise errors.  Also has several options for
    selecting what to include.
    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {
        'linenos': directives.flag,
        'tab-width': int,
        'language': directives.unchanged_required,
        'encoding': directives.encoding,
        'pyobject': directives.unchanged_required,
        'lines': directives.unchanged_required,
        'start-after': directives.unchanged_required,
        'end-before': directives.unchanged_required,
        'prepend': directives.unchanged_required,
        'append': directives.unchanged_required,
        'emphasize-lines': directives.unchanged_required,
        'fragment': directives.unchanged,
    }

    def run(self):
        document = self.state.document
        if not document.settings.file_insertion_enabled:
            return [document.reporter.warning('File insertion disabled',
                                              line=self.lineno)]
        env = document.settings.env
        rel_filename, filename = env.relfn2path(os.path.join(
            '/' + env.config.includefrags_base_dir, self.arguments[0])) ## !!!

        if 'pyobject' in self.options and 'lines' in self.options:
            return [document.reporter.warning(
                'Cannot use both "pyobject" and "lines" options',
                line=self.lineno)]

        encoding = self.options.get('encoding', env.config.source_encoding)
        codec_info = codecs.lookup(encoding)
        f = None
        try:
            f = codecs.StreamReaderWriter(open(filename, 'rb'),
                    codec_info[2], codec_info[3], 'strict')
            lines = f.readlines()
        except (IOError, OSError):
            return [document.reporter.warning(
                'Include file %r not found or reading it failed' % filename,
                line=self.lineno)]
        except UnicodeError:
            return [document.reporter.warning(
                'Encoding %r used for reading included file %r seems to '
                'be wrong, try giving an :encoding: option' %
                (encoding, filename))]
        finally:
            if f is not None:
                f.close()

        objectname = self.options.get('pyobject')
        if objectname is not None:
            from sphinx.pycode import ModuleAnalyzer
            analyzer = ModuleAnalyzer.for_file(filename, '')
            tags = analyzer.find_tags()
            if objectname not in tags:
                return [document.reporter.warning(
                    'Object named %r not found in include file %r' %
                    (objectname, filename), line=self.lineno)]
            else:
                lines = lines[tags[objectname][1]-1 : tags[objectname][2]-1]

        fragment = self.options.get('fragment')
        if fragment is not None:
            result = []
            key = None
            active = False
            for line in lines:
                line = line.rstrip()  # Strip line ending and trailing whitespace.
                line += '\n' # add back line ending
                if line.strip().startswith('//![') and line.strip().endswith(']'):
                    key = line.strip()[4:-1].strip()
                    if key == fragment:
                        active = not active
                        continue
                if active:
                    result.append(line)
            while result and not result[-1].strip():
                result.pop()
            lines = result

        linespec = self.options.get('lines')
        if linespec is not None:
            try:
                linelist = parselinenos(linespec, len(lines))
            except ValueError as err:
                return [document.reporter.warning(str(err), line=self.lineno)]
            # just ignore nonexisting lines
            nlines = len(lines)
            lines = [lines[i] for i in linelist if i < nlines]
            if not lines:
                return [document.reporter.warning(
                    'Line spec %r: no lines pulled from include file %r' %
                    (linespec, filename), line=self.lineno)]

        linespec = self.options.get('emphasize-lines')
        if linespec:
            try:
                hl_lines = [x+1 for x in parselinenos(linespec, len(lines))]
            except ValueError as err:
                return [document.reporter.warning(str(err), line=self.lineno)]
        else:
            hl_lines = None

        startafter = self.options.get('start-after')
        endbefore  = self.options.get('end-before')
        prepend    = self.options.get('prepend')
        append     = self.options.get('append')
        if startafter is not None or endbefore is not None:
            use = not startafter
            res = []
            for line in lines:
                if not use and startafter and startafter in line:
                    use = True
                elif use and endbefore and endbefore in line:
                    use = False
                    break
                elif use:
                    res.append(line)
            lines = res

        if prepend:
           lines.insert(0, prepend + '\n')
        if append:
           lines.append(append + '\n')

        text = ''.join(lines)
        if self.options.get('tab-width'):
            text = text.expandtabs(self.options['tab-width'])
        retnode = nodes.literal_block(text, text, source=filename)
        set_source_info(self, retnode)
        if self.options.get('language', ''):
            retnode['language'] = self.options['language']
        elif filename.endswith('.cpp'):
            retnode['language'] = 'cpp'
        elif filename.endswith('.stdout') or filename.endswith('.stderr'):
            retnode['language'] = 'console'
        if 'linenos' in self.options:
            retnode['linenos'] = True
        if hl_lines is not None:
            retnode['highlight_args'] = {'hl_lines': hl_lines}
        env.note_dependency(rel_filename)
        return [retnode]

# setup function to register the extension

def setup(app):
    app.add_config_value('includefrags_base_dir', 
                         '.', 
                         'env')
    app.add_directive('includefrags', IncludeFrags)

