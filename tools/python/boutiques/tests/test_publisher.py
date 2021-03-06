from boutiques import __file__ as bfile
from boutiques.publisher import ZenodoError
from boutiques.bosh import bosh
import json
import subprocess
import shutil
import tempfile
import os
import os.path as op
import sys
import mock
from boutiques_mocks import *
if sys.version_info < (2, 7):
    from unittest2 import TestCase
else:
    from unittest import TestCase


def mock_get_publish_then_update():
    mock_record = MockZenodoRecord(1234567, "Example Boutiques Tool")
    return ([mock_zenodo_test_api_fail(),
            mock_zenodo_test_api(),
            mock_zenodo_search([]),
            mock_zenodo_test_api_fail(),
            mock_zenodo_test_api(),
            mock_zenodo_search([mock_record])])


# for publishing updates with --replace option
def mock_get_no_search():
    return ([mock_zenodo_test_api_fail(),
            mock_zenodo_test_api()])


def mock_post_publish_then_update():
    return ([mock_zenodo_deposit(1234567),
            mock_zenodo_upload_descriptor(),
            mock_zenodo_publish(1234567),
            mock_zenodo_deposit_updated(1234567, 2345678),
            mock_zenodo_upload_descriptor(),
            mock_zenodo_publish(2345678)])


def mock_post_publish_update_only():
    return ([mock_zenodo_deposit_updated(1234567, 2345678),
            mock_zenodo_upload_descriptor(),
            mock_zenodo_publish(2345678)])


def mock_put():
    return mock_zenodo_update_metadata()


def mock_delete():
    return mock_zenodo_delete_files()


def mock_get_auth_fail():
    return mock_zenodo_test_api_fail()


class TestPublisher(TestCase):

    def get_examples_dir(self):
        return op.join(op.dirname(bfile),
                       "schema", "examples")

    @mock.patch('requests.get', side_effect=mock_get_publish_then_update())
    @mock.patch('requests.post', side_effect=mock_post_publish_then_update())
    @mock.patch('requests.put', return_value=mock_put())
    @mock.patch('requests.delete', return_value=mock_delete())
    def test_publication(self, mock_get, mock_post, mock_put, mock_delete):
        example1_dir = op.join(self.get_examples_dir(), "example1")
        example1_desc = op.join(example1_dir, "example1_docker.json")
        temp_descriptor = tempfile.NamedTemporaryFile(suffix=".json")
        shutil.copyfile(example1_desc, temp_descriptor.name)

        # Make sure that example1.json doesn't have a DOI yet
        with open(temp_descriptor.name, 'r') as fhandle:
            descriptor = json.load(fhandle)
            assert(descriptor.get('doi') is None)

        # Test publication of a descriptor that doesn't have a DOI
        doi = bosh(["publish",
                    temp_descriptor.name,
                    "--sandbox", "-y", "-v",
                    "--zenodo-token", "hAaW2wSBZMskxpfigTYHcuDrC"
                    "PWr2VeQZgBLErKbfF5RdrKhzzJi8i2hnN8r"])
        assert(doi)

        # Now descriptor should have a DOI
        with open(temp_descriptor.name, 'r') as fhandle:
            descriptor = json.load(fhandle)
            assert(descriptor.get('doi') == doi)

        # Test publication of a descriptor that already has a DOI
        with self.assertRaises(ZenodoError) as e:
            bosh(["publish",
                  temp_descriptor.name,
                  "--sandbox", "-y", "-v",
                  "--zenodo-token", "hAaW2wSBZMskxpfigTYHcuDrC"
                  "PWr2VeQZgBLErKbfF5RdrKhzzJi8i2hnN8r"])
        self.assertTrue("Descriptor already has a DOI" in str(e.exception))

        # Test publication of an updated version of the same descriptor
        example1_desc_updated = op.join(example1_dir,
                                        "example1_docker_updated.json")
        temp_descriptor_updated = tempfile.NamedTemporaryFile(suffix=".json")
        shutil.copyfile(example1_desc_updated, temp_descriptor_updated.name)

        with open(temp_descriptor_updated.name, 'r') as fhandle:
            descriptor_updated = json.load(fhandle)

        # Publish the updated version
        new_doi = bosh(["publish",
                        temp_descriptor_updated.name,
                        "--sandbox", "-y", "-v",
                        "--zenodo-token", "hAaW2wSBZMskxpfigTYHcuDrC"
                        "PWr2VeQZgBLErKbfF5RdrKhzzJi8i2hnN8r"])
        assert(new_doi)

        # Updated version of descriptor should have a new DOI
        with open(temp_descriptor_updated.name, 'r') as fhandle:
            descriptor_updated = json.load(fhandle)
            assert(descriptor_updated.get('doi') == new_doi)
            assert(descriptor_updated.get('doi') != doi)

    @mock.patch('requests.get', return_value=mock_get_auth_fail())
    def test_publisher_auth(self, mock_get):
        example1_dir = op.join(self.get_examples_dir(), "example1")

        # Bad token should fail
        with self.assertRaises(ZenodoError) as e:
            bosh(["publish",
                  op.join(example1_dir, "example1_docker.json"),
                  "--sandbox",
                  "-y", "-v", "--zenodo-token", "12345"])
        self.assertTrue("Cannot authenticate to Zenodo" in str(e.exception))

        # No token should fail
        with self.assertRaises(ZenodoError) as e:
            bosh(["publish",
                 op.join(example1_dir,
                         "example1_docker.json"),
                 "--sandbox", "-y", "-v"])
        self.assertTrue("Cannot authenticate to Zenodo" in str(e.exception))

        # Right token should work
        self.assertTrue(bosh, ["publish",
                               op.join(example1_dir,
                                       "example1_docker.json"),
                               "--sandbox", "-y", "-v",
                               "--zenodo-token",
                               "hAaW2wSBZMskxpfigTYHcuDrC"
                               "PWr2VeQZgBLErKbfF5RdrKhzzJ"
                               "i8i2hnN8r"])

        # Now no token should work (config file must have been updated)
        self.assertTrue(bosh, ["publish",
                               op.join(example1_dir,
                                       "example1_docker.json"),
                               "--sandbox", "-y", "-v"])

    @mock.patch('requests.get', return_value=mock_get_auth_fail())
    def test_publisher_auth_fail_cli(self, mock_get):
        example1_dir = op.join(self.get_examples_dir(), "example1")
        command = ("bosh publish " + op.join(example1_dir,
                                             "example1_docker.json") +
                   " --sandbox -y -v "
                   "--zenodo-token 12345")
        process = subprocess.Popen(command, shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        process.communicate()
        self.assertTrue(process.returncode)

    @mock.patch('requests.get', side_effect=mock_get_no_search())
    @mock.patch('requests.post', side_effect=mock_post_publish_update_only())
    @mock.patch('requests.put', return_value=mock_put())
    @mock.patch('requests.delete', return_value=mock_delete())
    def test_publication_replace_with_id(self, mock_get, mock_post, mock_put,
                                         mock_delete):
        example1_dir = op.join(self.get_examples_dir(), "example1")
        example1_desc = op.join(example1_dir, "example1_docker.json")
        temp_descriptor = tempfile.NamedTemporaryFile(suffix=".json")
        shutil.copyfile(example1_desc, temp_descriptor.name)

        # Make sure that example1.json doesn't have a DOI yet
        with open(temp_descriptor.name, 'r') as fhandle:
            descriptor = json.load(fhandle)
            assert (descriptor.get('doi') is None)

        # Publish an updated version of an already published descriptor
        doi = bosh(["publish",
                    temp_descriptor.name,
                    "--sandbox", "-y", "-v",
                    "--zenodo-token", "hAaW2wSBZMskxpfigTYHcuDrC"
                                      "PWr2VeQZgBLErKbfF5RdrKhzzJi8i2hnN8r",
                    "--id", "zenodo.1234567"])
        assert (doi)

        # Now descriptor should have a DOI
        with open(temp_descriptor.name, 'r') as fhandle:
            descriptor = json.load(fhandle)
            assert (descriptor.get('doi') == doi)

    @mock.patch('requests.get', side_effect=mock_get_no_search())
    @mock.patch('requests.post', side_effect=mock_post_publish_update_only())
    @mock.patch('requests.put', return_value=mock_put())
    @mock.patch('requests.delete', return_value=mock_delete())
    def test_publication_replace_no_id(self, mock_get, mock_post, mock_put,
                                       mock_delete):
        example1_dir = op.join(self.get_examples_dir(), "example1")
        example1_desc = op.join(example1_dir, "example1_docker_with_doi.json")
        temp_descriptor = tempfile.NamedTemporaryFile(suffix=".json")
        shutil.copyfile(example1_desc, temp_descriptor.name)

        # Make sure that descriptor has a DOI
        with open(temp_descriptor.name, 'r') as fhandle:
            descriptor = json.load(fhandle)
            assert (descriptor.get('doi') is not None)
            old_doi = descriptor['doi']

        # Publish an updated version of an already published descriptor
        doi = bosh(["publish",
                    temp_descriptor.name,
                    "--sandbox", "-y", "-v",
                    "--zenodo-token", "hAaW2wSBZMskxpfigTYHcuDrC"
                                      "PWr2VeQZgBLErKbfF5RdrKhzzJi8i2hnN8r",
                    "--replace"])
        assert (doi)

        # Now descriptor should have a DOI which should be different
        # than the old DOI
        with open(temp_descriptor.name, 'r') as fhandle:
            descriptor = json.load(fhandle)
            assert (descriptor.get('doi') == doi)
            assert(descriptor.get('doi') != old_doi)
