# Authors: Alexandre Gramfort <alexandre.gramfort@inria.fr>
#          Joan Massich <mailsik@gmail.com>
#
# License: BSD Style.

import os
from os import path as op
import numpy as np

from ...utils import _fetch_file, verbose, _TempDir, _check_pandas_installed
from ..utils import _get_path

BASE_URL = 'https://physionet.org/pn4/sleep-edfx/'
AGE_SLEEP_RECORDS = op.join(op.dirname(__file__), 'age_records.csv')
TEMAZEPAM_SLEEP_RECORDS = op.join(op.dirname(__file__),
                                  'temazepam_records.csv')


def _fetch_one(fname, hashsum, path, force_update):
    # Fetch the file
    url = BASE_URL + '/' + fname
    destination = op.join(path, fname)
    if not op.isfile(destination) or force_update:
        if op.isfile(destination):
            os.remove(destination)
        if not op.isdir(op.dirname(destination)):
            os.makedirs(op.dirname(destination))
        _fetch_file(url, destination, print_destination=False,
                    hash_=hashsum, hash_type='sha1')
    return destination


@verbose
def _data_path(path=None, force_update=False, update_path=None, verbose=None):
    """Get path to local copy of EEG Physionet age Polysomnography dataset URL.

    This is a low-level function useful for getting a local copy of a
    remote Polysomnography dataset [1]_ which is available at PhysioNet [2]_.

    Parameters
    ----------
    path : None | str
        Location of where to look for the data storing location.
        If None, the environment variable or config parameter
        ``MNE_DATASETS_PHYSIONET_SLEEP_PATH`` is used. If it doesn't exist, the
        "~/mne_data" directory is used. If the dataset
        is not found under the given path, the data
        will be automatically downloaded to the specified folder.
    force_update : bool
        Force update of the dataset even if a local copy exists.
    update_path : bool | None
        If True, set the MNE_DATASETS_PHYSIONET_SLEEP_PATH in mne-python
        config to the given path. If None, the user is prompted.
    verbose : bool, str, int, or None
        If not None, override default verbose level (see :func:`mne.verbose`).

    Returns
    -------
    path : list of str
        Local path to the given data file. This path is contained inside a list
        of length one, for compatibility.

    References
    ----------
    .. [1] B Kemp, AH Zwinderman, B Tuk, HAC Kamphuisen, JJL Oberyé. Analysis of
           a sleep-dependent neuronal feedback loop: the slow-wave microcontinuity
           of the EEG. IEEE-BME 47(9):1185-1194 (2000).
    .. [2] Goldberger AL, Amaral LAN, Glass L, Hausdorff JM, Ivanov PCh,
           Mark RG, Mietus JE, Moody GB, Peng C-K, Stanley HE. (2000)
           PhysioBank, PhysioToolkit, and PhysioNet: Components of a New
           Research Resource for Complex Physiologic Signals.
           Circulation 101(23):e215-e220
    """  # noqa: E501
    key = 'PHYSIONET_SLEEP_PATH'
    name = 'PHYSIONET_SLEEP'
    path = _get_path(path, key, name)
    return op.join(path, 'physionet-sleep-data')


def _update_sleep_temazepam_records(fname=TEMAZEPAM_SLEEP_RECORDS):
    """Help function to download Physionet's temazepam dataset records."""
    pd = _check_pandas_installed()
    tmp = _TempDir()

    # Download files checksum.
    sha1sums_url = BASE_URL + "SHA1SUMS"
    sha1sums_fname = op.join(tmp, 'sha1sums')
    _fetch_file(sha1sums_url, sha1sums_fname)

    # Download subjects info.
    subjects_url = BASE_URL + 'ST-subjects.xls'
    subjects_fname = op.join(tmp, 'ST-subjects.xls')
    _fetch_file(url=subjects_url, file_name=subjects_fname,
                hash_='f52fffe5c18826a2bd4c5d5cb375bb4a9008c885',
                hash_type='sha1')

    # Load and Massage the checksums.
    sha1_df = pd.read_csv(sha1sums_fname, sep='  ', header=None,
                          names=['sha', 'fname'], engine='python')
    select_age_records = (sha1_df.fname.str.startswith('ST') &
                          sha1_df.fname.str.endswith('edf'))
    sha1_df = sha1_df[select_age_records]
    sha1_df['id'] = [name[:6] for name in sha1_df.fname]

    # Load and massage the data.
    data = pd.read_excel(subjects_fname, header=[0, 1])
    data.index.name = 'subject'
    data.columns.names = [None, None]
    data = (data.set_index([('Subject - age - sex', 'Age'),
                            ('Subject - age - sex', 'M1/F2')], append=True)
                .stack(level=0).reset_index())

    data = data.rename(columns={('Subject - age - sex', 'Age'): 'age',
                                ('Subject - age - sex', 'M1/F2'): 'sex',
                                'level_3': 'drug'})
    data['id'] = ['ST7{0:02d}{1:1d}'.format(s, n)
                  for s, n in zip(data.subject, data['night nr'])]

    data = pd.merge(sha1_df, data, how='outer', on='id')
    data['record type'] = (data.fname.str.split('-', expand=True)[1]
                                     .str.split('.', expand=True)[0]
                                     .astype('category'))

    data = data.set_index(['id', 'subject', 'age', 'sex', 'drug',
                           'lights off', 'night nr', 'record type']).unstack()
    data = data.drop(columns=[('sha', np.nan), ('fname', np.nan)])
    data.columns = [l1 + '_' + l2 for l1, l2 in data.columns]
    data = data.reset_index().drop(columns=['id'])

    data['sex'] = (data.sex.astype('category')
                       .cat.rename_categories({1: 'male', 2: 'female'}))

    data['drug'] = data['drug'].str.split(expand=True)[0]
    data['subject_orig'] = data['subject']
    data['subject'] = data.index // 2  # to make sure index is from 0 to 21

    data.dropna(inplace=True)

    # Save the data.
    data.to_csv(fname, index=False)


def _update_sleep_age_records(fname=AGE_SLEEP_RECORDS):
    """Help function to download Physionet's age dataset records."""
    pd = _check_pandas_installed()
    tmp = _TempDir()

    # Download files checksum.
    sha1sums_url = BASE_URL + "SHA1SUMS"
    sha1sums_fname = op.join(tmp, 'sha1sums')
    _fetch_file(sha1sums_url, sha1sums_fname)

    # Download subjects info.
    subjects_url = BASE_URL + 'SC-subjects.xls'
    subjects_fname = op.join(tmp, 'SC-subjects.xls')
    _fetch_file(url=subjects_url, file_name=subjects_fname,
                hash_='0ba6650892c5d33a8e2b3f62ce1cc9f30438c54f',
                hash_type='sha1')

    # Load and Massage the checksums.
    sha1_df = pd.read_csv(sha1sums_fname, sep='  ', header=None,
                          names=['sha', 'fname'], engine='python')
    select_age_records = (sha1_df.fname.str.startswith('SC') &
                          sha1_df.fname.str.endswith('edf'))
    sha1_df = sha1_df[select_age_records]
    sha1_df['id'] = [name[:6] for name in sha1_df.fname]

    # Load and massage the data.
    data = pd.read_excel(subjects_fname)
    data = data.rename(index=str, columns={'sex (F=1)': 'sex',
                                           'LightsOff': 'lights off'})
    data['sex'] = (data.sex.astype('category')
                       .cat.rename_categories({1: 'female', 2: 'male'}))

    data['id'] = ['SC4{0:02d}{1:1d}'.format(s, n)
                  for s, n in zip(data.subject, data.night)]

    data = data.set_index('id').join(sha1_df.set_index('id')).dropna()

    data['record type'] = (data.fname.str.split('-', expand=True)[1]
                                     .str.split('.', expand=True)[0]
                                     .astype('category'))

    # data = data.set_index(['subject', 'night', 'record type'])
    data = data.reset_index().drop(columns=['id'])
    data = data[['subject', 'night', 'record type', 'age', 'sex', 'lights off',
                 'sha', 'fname']]

    # Save the data.
    data.to_csv(fname, index=False)


def _check_subjects(subjects, n_subjects):
    valid_subjects = np.arange(n_subjects)
    unknown_subjects = np.setdiff1d(subjects, valid_subjects)
    if unknown_subjects.size > 0:
        subjects_list = ', '.join([str(s) for s in unknown_subjects])
        raise ValueError('Only subjects 0 to {} are'
                         ' available from this dataset.'
                         ' Unknown subjects: {}'.format(n_subjects - 1,
                                                        subjects_list))
