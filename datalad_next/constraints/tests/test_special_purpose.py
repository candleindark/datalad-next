from io import StringIO
import pathlib
import pytest

from datalad.support.param import Parameter

from ..basic import (
    EnsureInt,
    EnsureStr,
    NoConstraint,
)
from ..compound import EnsureGeneratorFromFileLike
from ..formats import (
    EnsureJSON,
    EnsureURL,
    EnsureParsedURL,
)
from ..git import (
    EnsureGitRefName,
)
from ..parameter import EnsureParameterConstraint


def test_EnsureGitRefName():
    assert EnsureGitRefName().short_description() == '(single-level) Git refname'
    # standard branch name must work
    assert EnsureGitRefName()('main') == 'main'
    # normalize is on by default
    assert EnsureGitRefName()('/main') == 'main'
    with pytest.raises(ValueError):
        EnsureGitRefName(normalize=False)('/main')
    assert EnsureGitRefName(normalize=False)('main') == 'main'
    # no empty
    with pytest.raises(ValueError):
        EnsureGitRefName()('')
    with pytest.raises(ValueError):
        EnsureGitRefName()(None)
    # be able to turn off onelevel
    with pytest.raises(ValueError):
        EnsureGitRefName(allow_onelevel=False)('main')
    assert EnsureGitRefName(allow_onelevel=False)(
        'refs/heads/main') == 'refs/heads/main'
    # refspec pattern off by default
    with pytest.raises(ValueError):
        EnsureGitRefName()('refs/heads/*')
    assert EnsureGitRefName(refspec_pattern=True)(
        'refs/heads/*') == 'refs/heads/*'


def test_EnsureParameterConstraint():
    # most basic case, no value constraint
    c = EnsureParameterConstraint(NoConstraint())
    # invalid name
    with pytest.raises(ValueError):
        c({'4way': 123})
    assert c('some=value') == dict(some='value')
    # now some from a standard Parameter declaration
    c = EnsureParameterConstraint.from_parameter(
        Parameter(), 'whateverdefault')
    assert c('some=value') == dict(some='value')

    # want a bool
    c = EnsureParameterConstraint.from_parameter(
        Parameter(action="store_true"),
        False)
    assert c('some=off') == dict(some=False)
    with pytest.raises(ValueError):
        c('some=5')
    c = EnsureParameterConstraint.from_parameter(
        # argparse specific choice declaration without
        # any constraint
        Parameter(choices=['a', 'b']),
        # but specifically use a default that is not a valid choice
        None)
    assert c('choice=a') == dict(choice='a')
    # default is valid too
    assert c({'choice': None}) == dict(choice=None)
    # multi-item values
    c = EnsureParameterConstraint.from_parameter(
        Parameter(nargs=2),
        (None, None))
    assert c({'some': [3, 4]}) == dict(some=[3, 4])
    with pytest.raises(TypeError):
        c({'some': 3})
    with pytest.raises(ValueError):
        c({'some': [3, 4, 5]})
    # one or more items
    c = EnsureParameterConstraint.from_parameter(
        Parameter(nargs='*'),
        None)
    # always prefers a list, no item type conversion by default
    assert c('some=5') == dict(some=['5'])
    assert c({'some': [5, 2]}) == dict(some=[5, 2])
    # empty ok
    assert c({'some': []}) == dict(some=[])
    # at least one item
    c = EnsureParameterConstraint.from_parameter(
        Parameter(nargs='+', constraints=EnsureInt()),
        None)
    assert c('some=5') == dict(some=[5])
    assert c({'some': [5, 2]}) == dict(some=[5, 2])
    # empty not ok
    with pytest.raises(ValueError):
        c({'some': []})
    # complex case of iterables of length 2
    c = EnsureParameterConstraint.from_parameter(
        Parameter(nargs=2, constraints=EnsureInt(), action='append'),
        None)
    # no iterable does not violate
    assert c({'some': []}) == dict(some=[])
    assert c({'some': [[3, 2]]}) == dict(some=[[3, 2]])
    assert c({'some': [[3, 2], [5, 4]]}) == dict(some=[[3, 2], [5, 4]])
    # length mismatch
    with pytest.raises(ValueError):
        c({'some': [[3, 2], [1]]})
    # no iterable
    with pytest.raises(ValueError):
        c({'some': [3, [1, 2]]})
    with pytest.raises(ValueError):
        c({'some': 3})
    # overwrite an item constraint and nargs
    c = EnsureParameterConstraint.from_parameter(
        Parameter(nargs=2, constraints=EnsureInt(), action='append'),
        None,
        item_constraint=EnsureStr(),
        nargs=1)
    assert c({'some': ['5']}) == dict(some=['5'])
    # literal constraint label
    # this is no longer supported, but still works: test until removed
    with pytest.deprecated_call():
        c = EnsureParameterConstraint.from_parameter(
            Parameter(), 2, item_constraint='float')
    assert c('some=3') == dict(some=3.0)
    with pytest.raises(ValueError), \
            pytest.deprecated_call():
        EnsureParameterConstraint.from_parameter(
            Parameter(), 2, item_constraint='unknown')


nested_json = """\
{"name": "Alexa", "wins": [["two pair", "4♠"], ["two pair", "9♠"]]}
"""
nested_json_decoded = {
    "name": "Alexa",
    "wins": [["two pair", "4♠"],
             ["two pair", "9♠"]],
}
invalid_json = """\
{"name": BOOM!}
"""


def test_EnsureJSONLines():
    constraint = EnsureGeneratorFromFileLike(EnsureJSON())

    assert 'items of type "JSON" read from a file-like' \
        ==  constraint.short_description()

    # typical is "object", but any valid JSON value type must work
    assert list(constraint(StringIO("5"))) == [5]
    # unicode must work
    uc = "ΔЙקم๗あ"
    assert list(constraint(StringIO(f'"{uc}"'))) == [uc]
    assert list(constraint(StringIO(nested_json))) == [nested_json_decoded]

    with pytest.raises(ValueError) as e:
        list(constraint(StringIO(f'{nested_json}\n{invalid_json}')))


url_testcases = {
    "http://www.google.com": ['netloc','scheme',],
    "https://www.google.com": ['netloc','scheme',],
    "http://google.com": ['netloc','scheme',],
    "https://google.com": ['netloc','scheme',],
    "www.google.com": ['path',],
    "google.com": ['path',],
    "http://www.google.com/~as_db3.2123/134-1a": ['netloc','path','scheme',],
    "https://www.google.com/~as_db3.2123/134-1a": ['netloc','path','scheme',],
    "http://google.com/~as_db3.2123/134-1a": ['netloc','path','scheme',],
    "https://google.com/~as_db3.2123/134-1a": ['netloc','path','scheme',],
    "www.google.com/~as_db3.2123/134-1a": ['path',],
    "google.com/~as_db3.2123/134-1a": ['path',],
    # .co.uk top level
    "http://www.google.co.uk": ['netloc','scheme',],
    "https://www.google.co.uk": ['netloc','scheme',],
    "http://google.co.uk": ['netloc','scheme',],
    "https://google.co.uk": ['netloc','scheme',],
    "www.google.co.uk": ['path',],
    "google.co.uk": ['path',],
    "http://www.google.co.uk/~as_db3.2123/134-1a": ['netloc','path','scheme',],
    "https://www.google.co.uk/~as_db3.2123/134-1a": ['netloc','path','scheme',],
    "http://google.co.uk/~as_db3.2123/134-1a": ['netloc','path','scheme',],
    "https://google.co.uk/~as_db3.2123/134-1a": ['netloc','path','scheme',],
    "www.google.co.uk/~as_db3.2123/134-1a": ['path',],
    "google.co.uk/~as_db3.2123/134-1a": ['path',],
    "https://...": ['netloc', 'scheme',],
    "https://..": ['netloc', 'scheme',],
    "https://.": ['netloc', 'scheme',],
    "file:///mike/was/here": ['path','scheme',],
    "https://.google.com": ['netloc','scheme',],
    "https://..google.com": ['netloc','scheme',],
    "https://...google.com": ['netloc','scheme',],
    "https://.google..com": ['netloc','scheme',],
    "https://.google...com": ['netloc','scheme',],
    "https://...google..com": ['netloc','scheme',],
    "https://...google...com": ['netloc','scheme',],
    ".google.com": ['path',],
    ".google.co.": ['path',],
    "https://google.co.": ['netloc','scheme',],
}


def test_EnsureURL():
    assert EnsureURL().short_description() == 'URL'
    assert EnsureURL(
        required=['scheme', 'netloc']
    ).short_description() == "URL with required ['scheme', 'netloc'] component(s)"
    assert EnsureURL(
        forbidden=['fragment']
    ).short_description() == "URL with no ['fragment'] component(s)"
    assert EnsureURL(
        # yes, it need not make sense
        required=['a'], forbidden=['b']
    ).short_description() == "URL with required ['a'] and with no ['b'] component(s)"

    any_url = EnsureURL()
    for tc in url_testcases.keys():
        any_url(tc)

    for t in ['netloc', 'path', 'scheme']:
        cnotag = EnsureURL(forbidden=[t])
        cnotag_parsed = EnsureParsedURL(forbidden=[t])
        for url, tags in url_testcases.items():
            if t in tags:
                with pytest.raises(ValueError) as e:
                    cnotag(url)
                assert f"forbidden '{t}'" in str(e)
            else:
                cnotag(url)
                cnotag_parsed(url)
        ctag = EnsureURL(required=[t])
        ctag_parsed = EnsureParsedURL(required=[t])
        for url, tags in url_testcases.items():
            if t not in tags:
                with pytest.raises(ValueError) as e:
                    ctag(url)
                assert f"missing '{t}'" in str(e)
            else:
                ctag(url)
                ctag_parsed(url)