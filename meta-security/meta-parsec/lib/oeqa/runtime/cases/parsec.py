# Copyright (C) 2022 Armin Kuster <akuster808@gmail.com>
# Copyright (C) 2022 Anton Antonov <Anton.Antonov@arm.com>
#
import re
from tempfile import mkstemp

from oeqa.runtime.case import OERuntimeTestCase
from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.decorator.package import OEHasPackage
from oeqa.core.decorator.data import skipIfNotFeature

class ParsecTest(OERuntimeTestCase):
    @classmethod
    def setUpClass(cls):
        cls.toml_file = '/etc/parsec/config.toml'

    def setUp(self):
        super(ParsecTest, self).setUp()
        if 'systemd' in self.tc.td['DISTRO_FEATURES']:
            self.parsec_status='systemctl status -l parsec'
            self.parsec_reload='systemctl restart parsec'
        else:
            self.parsec_status='pgrep -l parsec'
            self.parsec_reload='/etc/init.d/parsec reload'

    def copy_subconfig(self, cfg, provider):
        """ Copy a provider configuration to target and append it to Parsec config """

        tmp_fd, tmp_path = mkstemp()
        with os.fdopen(tmp_fd, 'w') as f:
            f.write('\n'.join(cfg))

        (status, output) = self.target.copyTo(tmp_path, "%s-%s" % (self.toml_file, provider))
        self.assertEqual(status, 0, msg='File could not be copied.\n%s' % output)
        status, output = self.target.run('cat %s-%s >>%s' % (self.toml_file, provider, self.toml_file))
        os.remove(tmp_path)

    def check_parsec_providers(self, provider=None, prov_id=None):
        """ Get Parsec providers list and check for one if defined """

        status, output = self.target.run(self.parsec_status)
        self.assertEqual(status, 0, msg='Parsec service is not running.\n%s' % output)

        status, output = self.target.run('parsec-tool list-providers')
        self.assertEqual(status, 0, msg='Cannot get a list of Parsec providers.\n%s' % output)
        if provider and prov_id:
            self.assertIn("ID: 0x0%d (%s provider)" % (prov_id, provider),
                          output, msg='%s provider is not configured.' % provider)

    def run_cli_tests(self, prov_id=None):
        """ Run Parsec CLI end-to-end tests against one or all providers """

        status, output = self.target.run('parsec-cli-tests.sh %s' % ("-%d" % prov_id if prov_id else ""))
        self.assertEqual(status, 0, msg='Parsec CLI tests failed.\n %s' % output)

    @OEHasPackage(['parsec-service'])
    @OETestDepends(['ssh.SSHTest.test_ssh'])
    def test_all_providers(self):
        """ Test Parsec service with all pre-defined providers """

        self.check_parsec_providers()
        self.run_cli_tests()

    def configure_tpm_provider(self):
        """ Create Parsec TPM provider configuration """

        cfg = [
                '',
                '[[provider]]',
                'name = "tpm-provider"',
                'provider_type = "Tpm"',
                'key_info_manager = "sqlite-manager"',
                'tcti = "swtpm:port=2321"',
                'owner_hierarchy_auth = ""',
              ]
        self.copy_subconfig(cfg, "TPM")

        cmds = [
                'mkdir /tmp/myvtpm',
                'swtpm socket -d --tpmstate dir=/tmp/myvtpm --tpm2 --ctrl type=tcp,port=2322 --server type=tcp,port=2321 --flags not-need-init',
                'tpm2_startup -c -T "swtpm:port=2321"',
                self.parsec_reload,
               ]

        for cmd in cmds:
            status, output = self.target.run(cmd)
            self.assertEqual(status, 0, msg='\n'.join([cmd, output]))

    @OEHasPackage(['parsec-service'])
    @OEHasPackage(['swtpm'])
    @skipIfNotFeature('tpm2','Test parsec_tpm_provider requires tpm2 to be in DISTRO_FEATURES')
    @OETestDepends(['ssh.SSHTest.test_ssh', 'parsec.ParsecTest.test_all_providers'])
    def test_tpm_provider(self):
        """ Configure and test Parsec TPM provider with swtpm as a backend """

        prov_id = 3
        self.configure_tpm_provider()
        self.check_parsec_providers("TPM", prov_id)
        self.run_cli_tests(prov_id)

    def configure_pkcs11_provider(self):
        """ Create Parsec PKCS11 provider configuration """

        status, output = self.target.run('softhsm2-util --init-token --free --label "Parsec Service" --pin 123456 --so-pin 123456')
        self.assertEqual(status, 0, msg='Failed to init PKCS11 token.\n%s' % output)

        slot = re.search('The token has been initialized and is reassigned to slot (\d*)', output)
        if slot is None:
            self.fail('Failed to get PKCS11 slot serial number.\n%s' % output)
        self.assertNotEqual(slot.group(1), None, msg='Failed to get PKCS11 slot serial number.\n%s' % output)

        cfg = [
                '',
                '[[provider]]',
                'name = "pkcs11-provider"',
                'provider_type = "Pkcs11"',
                'key_info_manager = "sqlite-manager"',
                'library_path = "/usr/lib/softhsm/libsofthsm2.so"',
                'slot_number = %s' % slot.group(1),
                'user_pin = "123456"',
                'allow_export = true',
              ]
        self.copy_subconfig(cfg, "PKCS11")

        status, output = self.target.run('for d in /var/lib/softhsm/tokens/*; do chown -R parsec $d; done')
        status, output = self.target.run(self.parsec_reload)
        self.assertEqual(status, 0, msg='Failed to reload Parsec.\n%s' % output)

    @OEHasPackage(['parsec-service'])
    @OEHasPackage(['softhsm'])
    @OETestDepends(['ssh.SSHTest.test_ssh', 'parsec.ParsecTest.test_all_providers'])
    def test_pkcs11_provider(self):
        """ Configure and test Parsec PKCS11 provider with softhsm as a backend """

        prov_id = 2
        self.configure_pkcs11_provider()
        self.check_parsec_providers("PKCS #11", prov_id)
        self.run_cli_tests(prov_id)
