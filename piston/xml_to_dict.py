'''
XMLtoDict.py
Author: Tom Coote
Date: 20th December 2009

This is licensed under GPL (http://www.opensource.org/licenses/gpl-license.php) licenses.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import xml.etree.ElementTree as ET
import re
def _updateDict(d, key, update):
    if isinstance(d.get(key), dict):
        d[key].update(update)
    else:
        d[key] = update

def _getValue(val):
    ''' 
    If the value can be turned into an integer then do that
    else return it unchanged.
    '''
    return val

#    if re.match(r'^\d+$', val or ''):
#        return int(val)
#    else:
#        return val

def _parseNode(node):
    ''' Turn an XML node into a dictionary '''
    the_dict = {}

    children = node.getchildren()
    if len(children) > 0:
        # look for what can be determined as a list of XML tags
        # if all tags at the same level are named the same then we
        # can turn those into a list
#        tag_name_list = children[0].tag
#        for child in children:
#            if tag_name_list != child.tag:
#                tag_name_list = False
#                break
#
#        if tag_name_list:
#            # we found a list so place the values of each child into a list
#            # against the current nodes tag name in the dictionary
##            _updateDict(the_dict, node.tag, { child.tag: [_parseNode(child)[child.tag] for child in children] })
#            the_dict[node.tag] = [_parseNode(child)[child.tag] for child in children]
#        else:
            # the child nodes were not a list so parse each of them as their own
            # dictionary against the current nodes tag name in the dictionary
        child_dic = {}
        for child in children:
            child_dic.update(_parseNode(child))

#            _updateDict(the_dict, node.tag, child_dic)
        the_dict[node.tag] = child_dic

    else:
        # the node we are currently parsing has no child nodes so
        # add it's text as the value against the current node tag name in 
        # the dictionary
#        _updateDict(the_dict, node.tag, _getValue(node.text))
        the_dict[node.tag] = _getValue(node.text)

    if node.attrib.items():
        # the node has attributes so parse them as if they were child nodes by adding
        # them as their own dictionaries against the current nodes tag name in the dictionary
        attribs_dic = {}
        for k, v in node.attrib.items():
            attribs_dic[k] = _getValue(v)

        _updateDict(the_dict, node.tag, attribs_dic)


    return the_dict

def fromstring(s):
    '''
    Given a string representation of some XML, return
    a python dictionary.
    '''
    if not s:
        return None
    
    xml = ET.fromstring(s)
    return _parseNode(xml)