# This file is part of the Hotwire Shell project API.

# Copyright (C) 2008 Colin Walters <walters@verbum.org>

# Permission is hereby granted, free of charge, to any person obtaining a copy 
# of this software and associated documentation files (the "Software"), to deal 
# in the Software without restriction, including without limitation the rights 
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies 
# of the Software, and to permit persons to whom the Software is furnished to do so, 
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all 
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE X CONSORTIUM BE 
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, 
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR 
# THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import sys

is_jython = sys.platform.startswith('java')

get_unichar_category = None
if is_jython:
    import java
    def jython_get_unichar_category(c):
        return java.lang.Character.getType(ord(c))
    get_unichar_category = jython_get_unichar_category
else:
    import unicodedata
    def unicodedata_get_unichar_category(c):
        return unicodedata.category(c)
    get_unichar_category = unicodedata_get_unichar_category

is_category_letter = None
if is_jython:
    import java
    def jython_is_category_letter(cat):
        return cat in (java.lang.Character.LOWERCASE_LETTER, java.lang.Character.UPPERCASE_LETTER,
                       java.lang.Character.TITLECASE_LETTER)
    is_category_letter = jython_is_category_letter
else:
    import unicodedata
    def unicodedata_is_category_letter(cat):
        return cat[0] == 'L'
    is_category_letter = unicodedata_is_category_letter

is_category_number = None
if is_jython:
    import java
    def jython_is_category_number(cat):
        return cat in (java.lang.Character.DECIMAL_DIGIT_NUMBER,
                       java.lang.Character.LETTER_NUMBER,
                       java.lang.Character.OTHER_NUMBER)
    is_category_number = jython_is_category_number
else:
    import unicodedata
    def unicodedata_is_category_number(cat):
        return cat[0] == 'N'
    is_category_number = unicodedata_is_category_number

is_category_whitespace = None
if is_jython:
    import java
    def jython_is_category_whitespace(cat):
        return cat in (java.lang.Character.PARAGRAPH_SEPARATOR,
                       java.lang.Character.SPACE_SEPARATOR)
    is_category_whitespace = jython_is_category_whitespace
else:
    import unicodedata
    def unicodedata_is_category_whitespace(cat):
        return cat[0] == 'Z'
    is_category_whitespace = unicodedata_is_category_whitespace
