import re

def sub_markup(text, input_leader, output_leader, input_trailer=None, output_trailer=None):

    if input_trailer is None:
        input_trailer = input_leader
    if output_trailer is None:
        output_trailer = output_leader

    # within the following pattern, (?<!\w) is a ne (?!\w) is a negative look-ahead assertion that asserts
    # the same about the next character.

    matcher = (
        r'(?<!\w)'            # negative look-behind assertion: checks that the
                              # previous character is not a word character.
        + re.escape(input_leader)
        + r'(\w|\S.*?\S)'     # body: either a single word character, or a
                              # series of two or more non-newlines which start
                              # and end with a non-space character
        + re.escape(input_trailer)
        + r'(?!\w)'           # negative look-ahead assertion: checks that the
                              # next character is not a word character.
    )

    replacement = (
        output_leader + r'\1' + output_trailer
    )

    return re.sub(matcher, replacement, text)


def to_markdown(text):
    if text is None:
        return ""

    text = text.replace('\r\n', '\n')

    # suffix @ with zwsp to stop github linkifying
    text = text.replace('@', '@&#8203;')

    # header text
    def header(m):
        return '#' * int(m.group(1))
    text = re.sub(r'^h([0-6])\.', header, text, 0, re.M)

    # *bold*
    text = sub_markup(text, '*', '**')

    # _underlined_ needs no change

    # {{monospaced}}
    text = sub_markup(text, '{{', '`', '}}', '`')

    # ??citation??
    text = sub_markup(text, '??', '<cite>', '??', '</cite>')

    # +inserted+
    text = sub_markup(text, '+', '<ins>', '+', '</ins>')

    # ^superscript^
    text = sub_markup(text, '^', '<sup>', '^', '</sup>')

    # ~subscript~
    text = sub_markup(text, '~', '<sub>', '~', '</sub>')

    # -strikethrough-
    text = sub_markup(text, '-', '~~')

    # code quote
    text = re.sub(r' *{code:([a-z]+)}', r'```\1', text)
    text = re.sub(r' *{code[^}]*}', r'```', text)
    text = re.sub(r' *{noformat}', r'```', text)

    def quote(m):
        return re.sub('^', '>', m.group(1), 0, re.M)+"\n\n"
    text = re.sub(r'{quote}\n+(.*?)\n{quote}\n*', quote, text, 0, re.S)

    # hyperlinks
    text = re.sub(r'(?<!\w)\[(.+?)\|(.+?)\](?!\w)', r'[\1](\2)', text)
    # text = re.sub(r'\[(.+?)\]([^\(]*)', r'<\1>\2', text)

    return text


if __name__ == '__main__':
    def expect_eq(input, expected_output):
        actual = to_markdown(input)
        assert actual == expected_output, "Expected '%r' to convert to '%r' but gave '%r'" % (
            input, expected_output, actual
        )

    expect_eq("*bold*", "**bold**")
    expect_eq("-strike- me -down-", "~~strike~~ me ~~down~~")

    # ``` only works when not indented
    expect_eq("""words
    {code}
    code
    {code}
""", """words
```
    code
```
""")

    expect_eq("""{quote}
text
{quote}
abc
""", """>text

abc
""")

    expect_eq("""here

{quote}

words

more words

{quote}

there
""", """here

>words
>
>more words
>

there
""")
