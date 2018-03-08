from pathlib import Path
from scipy.sparse import dok_matrix
import json
import numpy as np
import os
import pytest
import tempfile

from bw_presamples import *
from bw_presamples.errors import *
try:
    from bw2data import mapping
    from bw2data.tests import bw2test
except ImportError:
    bw2test = pytest.mark.skip


class MockLCA:
    def __init__(self):
        self.matrix = dok_matrix((5, 5))
        for i in range(5):
             for j in range(5):
                 self.matrix[i, j] = 0
        self.row_dict = {x: 2 * x for x in range(5)}
        self.col_dict = {x: 3 * x for x in range(5)}

@pytest.fixture
def tempdir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)

@pytest.fixture
@bw2test
def package():
    a = np.ones(shape=(3, 4)) * 100
    b = [(1, 1), (1, 2), (2, 3)]
    metadata = {
        'row from label': 'f1',
        'row to label': 'f3',
        'row dict': 'row_dict',
        'col from label': 'f2',
        'col to label': 'f4',
        'col dict': 'col_dict',
        'matrix': 'matrix'
    }
    frmt = lambda x: (x[0], x[1], x[0], x[1])
    dtype = [
        ('f1', np.uint32),
        ('f2', np.uint32),
        ('f3', np.uint32),
        ('f4', np.uint32),
    ]
    id_, dirpath = create_presamples_package(
        [(a, b, 'mock', dtype, frmt, metadata)],
    )
    return dirpath

def test_init(package):
    mp = MatrixPresamples([package])
    assert not mp.empty
    assert len(mp.data) == 1
    assert 'id' in mp.data[0]
    assert 'name' in mp.data[0]
    assert len(mp.data[0]['resources']) == 1
    resources = mp.data[0]['resources'][0]
    assert resources['type'] == 'mock'
    assert resources['matrix'] == 'matrix'
    for key in ('row from label', 'row to label', 'row dict',
                'col from label', 'col to label', 'col dict'):
        assert key in resources
    assert isinstance(resources['samples'], IrregularPresamplesArray)
    assert isinstance(resources['indices'], np.ndarray)

def test_update_matrices(package):
    mp = MatrixPresamples([package])
    lca = MockLCA()
    mp.update_matrices(lca)
    assert lca.matrix[1, 1] == 100
    assert lca.matrix[1, 2] == 100
    assert lca.matrix[2, 3] == 100
    assert lca.matrix.sum() == 300

def test_update_matrices_skip_missing_matrix(package):
    class WrongLCA:
        def __init__(self):
            self.wrong = dok_matrix((5, 5))
            for i in range(5):
                 for j in range(5):
                     self.wrong[i, j] = 0
            self.row_dict = {x: 2 * x for x in range(5)}
            self.col_dict = {x: 3 * x for x in range(5)}

    mp = MatrixPresamples([package])
    lca = WrongLCA()
    mp.update_matrices(lca)
    assert not lca.wrong.sum()

@bw2test
def test_update_matrices_technosphere():
    mapping.add('ABCDEF')
    for x, y in enumerate('ABCDEF'):
        assert mapping[y] == x + 1

    # 0 is production, 3 is substitution
    t1 = [('A', 'A', 0), ('A', 'B', 1), ('B', 'C', 3)]
    t2 = np.arange(3).reshape((3, 1)) + 10
    _, dirpath = create_presamples_package([(t2, t1, 'technosphere')])

    class LCA:
        def __init__(self):
            self.technosphere_matrix = dok_matrix((5, 5))
            for i in range(5):
                 for j in range(5):
                     self.technosphere_matrix[i, j] = 0
            self._activity_dict = {x: x-1 for x in range(1, 7)}
            self._product_dict = self._activity_dict

    lca = LCA()
    mp = MatrixPresamples([dirpath])
    mp.index_arrays(lca)
    mp.update_matrices(lca)
    assert lca.technosphere_matrix[0, 0] == 10
    assert lca.technosphere_matrix[0, 1] == -11
    assert lca.technosphere_matrix[1, 2] == 12
    assert lca.technosphere_matrix.sum() == 10 - 11 + 12

@bw2test
def test_update_matrices_one_dimensional():
    mapping.add('ABCDEF')
    for x, y in enumerate('ABCDEF'):
        assert mapping[y] == x + 1

    # 0 is production, 3 is substitution
    t1 = list('ACD')
    t2 = np.arange(3).reshape((3, 1)) + 10
    _, dirpath = create_presamples_package([(t2, t1, 'cf')])

    class LCA:
        def __init__(self):
            self.characterization_matrix = dok_matrix((5, 5))
            for i in range(5):
                 for j in range(5):
                     self.characterization_matrix[i, j] = 0
            self._biosphere_dict = {x: x-1 for x in range(1, 7)}

    lca = LCA()
    mp = MatrixPresamples([dirpath])
    mp.index_arrays(lca)
    mp.update_matrices(lca)
    assert lca.characterization_matrix[0, 0] == 10
    assert lca.characterization_matrix[2, 2] == 11
    assert lca.characterization_matrix[3, 3] == 12
    assert lca.characterization_matrix.sum() == 10 + 11 + 12

def test_index_arrays(package):
    mp = MatrixPresamples([package])
    lca = MockLCA()
    assert 'indexed' not in mp.data[0]['resources'][0]
    mp.index_arrays(lca)
    expected = [(1, 1, 2, 3), (1, 2, 2, 6), (2, 3, 4, 9)]
    assert mp.data[0]['resources'][0]['indices'].tolist() == expected
    assert mp.data[0]['resources'][0]['indexed']

def test_index_arrays_already_indexed(package):
    mp = MatrixPresamples([package])
    lca = MockLCA()
    assert 'indexed' not in mp.data[0]['resources'][0]
    expected = [(1, 1, 1, 1), (1, 2, 1, 2), (2, 3, 2, 3)]
    assert mp.data[0]['resources'][0]['indices'].tolist() == expected
    mp.index_arrays(lca)
    expected = [(1, 1, 2, 3), (1, 2, 2, 6), (2, 3, 4, 9)]
    assert mp.data[0]['resources'][0]['indices'].tolist() == expected
    assert mp.data[0]['resources'][0]['indexed']
    lca.row_dict = {x: 0 for x in range(5)}
    lca.col_dict = {x: 0 for x in range(5)}
    mp.index_arrays(lca)
    assert mp.data[0]['resources'][0]['indices'].tolist() == expected

def test_index_arrays_missing_row_dict(package):
    mp = MatrixPresamples([package])
    lca = MockLCA()
    del lca.row_dict
    expected = [(1, 1, 1, 1), (1, 2, 1, 2), (2, 3, 2, 3)]
    assert mp.data[0]['resources'][0]['indices'].tolist() == expected
    mp.index_arrays(lca)

def test_index_arrays_missing_col_dict(package):
    mp = MatrixPresamples([package])
    lca = MockLCA()
    del lca.col_dict
    expected = [(1, 1, 1, 1), (1, 2, 1, 2), (2, 3, 2, 3)]
    assert mp.data[0]['resources'][0]['indices'].tolist() == expected
    mp.index_arrays(lca)

def test_functionality_with_empty(tempdir):
    datapackage = {
        "name": "foo",
        "id": "one",
        "profile": "data-package",
        "resources": []
    }
    with open(tempdir / "datapackage.json", "w", encoding='utf-8') as f:
        json.dump(datapackage, f)
    mp = MatrixPresamples([tempdir])
    assert mp.empty
    mp.index_arrays(None)
    mp.update_matrices(None)

def test_validate_dirpath_missing_datapackage(package):
    os.unlink(package / "datapackage.json")
    with pytest.raises(AssertionError):
        MatrixPresamples([package])

def test_validate_dirpath_missing_samples(package):
    for fp in os.listdir(package):
        if "samples.npy" in fp:
            os.unlink(package / fp)
    with pytest.raises(AssertionError):
        MatrixPresamples([package])

def test_validate_dirpath_altered_samples(package):
    for fp in os.listdir(package):
        if "samples.npy" in fp:
            with open(package / fp, "w") as f:
                f.write("woops")
    with pytest.raises(AssertionError):
        MatrixPresamples([package])

def test_validate_dirpath_missing_indices(package):
    for fp in os.listdir(package):
        if "indices.npy" in fp:
            os.unlink(package / fp)
    with pytest.raises(AssertionError):
        MatrixPresamples([package])

def test_validate_dirpath_altered_indices(package):
    for fp in os.listdir(package):
        if "indices.npy" in fp:
            with open(package / fp, "w") as f:
                f.write("woops")
    with pytest.raises(AssertionError):
        MatrixPresamples([package])

@bw2test
def test_seed_functions():
    a = np.arange(12).reshape((3, 4))
    b = [(1, 1), (1, 2), (2, 3)]
    metadata = {
        'row from label': 'f1',
        'row to label': 'f3',
        'row dict': 'row_dict',
        'col from label': 'f2',
        'col to label': 'f4',
        'col dict': 'col_dict',
        'matrix': 'matrix'
    }
    frmt = lambda x: (x[0], x[1], x[0], x[1])
    dtype = [
        ('f1', np.uint32),
        ('f2', np.uint32),
        ('f3', np.uint32),
        ('f4', np.uint32),
    ]
    _, dirpath = create_presamples_package(
        [(a, b, 'mock', dtype, frmt, metadata)],
    )
    mp = MatrixPresamples([dirpath], 987654321)
    sampler = mp.data[0]['resources'][0]['samples']
    first = [sampler.sample().sum() for _ in range(100)]
    mp = MatrixPresamples([dirpath], 987654321)
    sampler = mp.data[0]['resources'][0]['samples']
    second = [sampler.sample().sum() for _ in range(100)]
    assert first == second

    mp = MatrixPresamples([dirpath], 12345)
    sampler = mp.data[0]['resources'][0]['samples']
    third = [sampler.sample().sum() for _ in range(100)]
    assert first != third


@pytest.fixture
def mp():
    class Mock(MatrixPresamples):
        def __init__(self):
            pass

    return Mock()

@pytest.fixture
def mock_ipa(monkeypatch):
    class FakeIPA:
        def __init__(self, one, two=None):
            self.one = one
            self.two = two

    monkeypatch.setattr(
        'bw_presamples.matrix_presamples.IrregularPresamplesArray',
        FakeIPA
    )

def test_consolidate_mismatched_matrices(package, mp):
    group = [{'matrix': 'a'}, {'matrix': 'b'}]
    with pytest.raises(AssertionError):
        mp.consolidate(package, group, None)

def test_consolidate_conficting_row_labels(mp):
    data = [
        {
            'row from label': 'f1',
            'row to label': 'f3',
            'row dict': 'row_dict',
            'col from label': 'f1',
            'col to label': 'f3',
            'col dict': 'col_dict',
            'matrix': 'm'
        }, {
            'row from label': 'f1',
            'row to label': 'f3',
            'row dict': 'row_dict',
            'col from label': '1f',
            'col to label': 'f3',
            'col dict': 'col_dict',
            'matrix': 'm'
        }
    ]
    with pytest.raises(ConflictingLabels):
        mp.consolidate(None, data)

def test_consolidate_conflicting_col_labels(mp):
    data = [
        {
            'row from label': 'f1',
            'row to label': 'f3',
            'row dict': 'row_dict',
            'matrix': 'm'
        }, {
            'row from label': '1f',
            'row to label': 'f3',
            'row dict': 'row_dict',
            'matrix': 'm'
        }
    ]
    with pytest.raises(ConflictingLabels):
        mp.consolidate(None, data)

def test_consolidate_conflicting_indices(mp, tempdir):
    a = np.ones(shape=(3, 4)) * 100
    b = [(1, 1), (1, 2), (2, 3)]
    c = np.ones(shape=(2, 4)) * 200
    d = [(10, 11), (12, 13)]
    metadata = {
        'row from label': 'f1',
        'row to label': 'f3',
        'row dict': 'row_dict',
        'col from label': 'f2',
        'col to label': 'f4',
        'col dict': 'col_dict',
        'matrix': 'matrix'
    }
    frmt = lambda x: (x[0], x[1], x[0], x[1])
    dtype_one = [
        ('f1', np.uint32),
        ('f2', np.uint32),
        ('f3', np.uint32),
        ('f4', np.uint32),
    ]
    dtype_two = [
        ('f1', np.int64),
        ('f2', np.int64),
        ('f3', np.int64),
        ('f4', np.int64),
    ]
    id_, dirpath = create_presamples_package([
            (a, b, 'mock', dtype_one, frmt, metadata),
            (c, d, 'mock', dtype_two, frmt, metadata),
        ], dirpath=tempdir
    )
    with pytest.raises(IncompatibleIndices):
        mp.consolidate(
            dirpath,
            PresamplesPackage(dirpath).metadata['resources']
        )

def test_consolidate_single_group(mock_ipa, mp, tempdir):
    a = np.ones(shape=(3, 4)) * 100
    b = [(1, 1), (1, 2), (2, 3)]

    c = np.ones(shape=(2, 4)) * 200
    d = [(10, 11), (12, 13)]

    metadata = {
        'row from label': 'f1',
        'row to label': 'f3',
        'row dict': 'row_dict',
        'col from label': 'f2',
        'col to label': 'f4',
        'col dict': 'col_dict',
        'matrix': 'matrix'
    }
    frmt = lambda x: (x[0], x[1], x[0], x[1])
    dtype = [
        ('f1', np.uint32),
        ('f2', np.uint32),
        ('f3', np.uint32),
        ('f4', np.uint32),
    ]
    id_, dirpath = create_presamples_package([
            (a, b, 'mock', dtype, frmt, metadata),
            (c, d, 'mock', dtype, frmt, metadata),
        ], dirpath=tempdir
    )

    expected = [
        f'{id_}.0.samples.npy',
        f'{id_}.0.indices.npy',
        f'{id_}.1.samples.npy',
        f'{id_}.1.indices.npy',
        'datapackage.json'
    ]
    assert sorted(os.listdir(dirpath)) == sorted(expected)

    results = mp.consolidate(dirpath, PresamplesPackage(dirpath).metadata['resources'])
    expected = [
        (dirpath / f'{id_}.0.samples.npy', [3, 4]),
        (dirpath / f'{id_}.1.samples.npy', [2, 4]),
    ]
    ipa = results['samples']
    assert ipa.one == expected
    assert ipa.two is None

def test_consolidate_multiple_groups(mock_ipa, tempdir):
    a = np.ones(shape=(4, 4)) * 100
    b = [(1, 1), (1, 2), (2, 3), (4, 5)]
    c = np.ones(shape=(3, 4)) * 200
    d = [(21, 21), (21, 22), (22, 23)]
    e = np.ones(shape=(2, 4)) * 300
    f = [(10, 11), (12, 13)]
    g = np.ones(shape=(1, 4)) * 400
    h = [(30, 31)]
    metadata_one = {
        'row from label': 'f1',
        'row to label': 'f3',
        'row dict': 'row_dict',
        'col from label': 'f2',
        'col to label': 'f4',
        'col dict': 'col_dict',
        'matrix': 'rude'
    }
    metadata_two = {
        'row from label': 'f1',
        'row to label': 'f3',
        'row dict': 'row_dict',
        'col from label': 'f2',
        'col to label': 'f4',
        'col dict': 'col_dict',
        'matrix': 'polite'
    }
    frmt = lambda x: (x[0], x[1], x[0], x[1])
    dtype = [
        ('f1', np.uint32),
        ('f2', np.uint32),
        ('f3', np.uint32),
        ('f4', np.uint32),
    ]
    id_one, dirpath_one = create_presamples_package([
            (a, b, 'mock', dtype, frmt, metadata_one),
            (e, f, 'mock', dtype, frmt, metadata_one),
        ], dirpath=tempdir
    )
    id_two, dirpath_two = create_presamples_package([
            (c, d, 'mock', dtype, frmt, metadata_two),
            (g, h, 'mock', dtype, frmt, metadata_two),
        ], dirpath=tempdir
    )

    mp = MatrixPresamples([dirpath_one, dirpath_two])
    expected = np.array([
        ( 1,  1,  1,  1),
        ( 1,  2,  1,  2),
        ( 2,  3,  2,  3),
        ( 4,  5,  4,  5),
        (10, 11, 10, 11),
        (12, 13, 12, 13)
    ])
    for x, y in zip(mp.data[0]['resources'][0]['indices'], expected):
        assert np.allclose(list(x), y)

    expected = np.array([
        (21, 21, 21, 21),
        (21, 22, 21, 22),
        (22, 23, 22, 23),
        (30, 31, 30, 31),
    ])
    for x, y in zip(mp.data[1]['resources'][0]['indices'], expected):
        assert np.allclose(list(x), y)

    assert mp.data[0]['resources'][0]['samples'].two is None
    assert mp.data[0]['resources'][0]['samples'].one[0][1] == [4, 4]
    assert mp.data[0]['resources'][0]['samples'].one[1][1] == [2, 4]
    assert mp.data[1]['resources'][0]['samples'].two is None
    assert mp.data[1]['resources'][0]['samples'].one[0][1] == [3, 4]
    assert mp.data[1]['resources'][0]['samples'].one[1][1] == [1, 4]