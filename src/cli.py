import click

from apps.akaunting.akaunting_cli import akaunting_cli
from apps.chatwoot.chatwoot_cli import chatwoot_cli
from apps.frappecrm.frappecrm_cli import frappecrm_cli
from apps.frappehelpdesk.frappehelpdesk_cli import frappehelpdesk_cli
from apps.frappehrms.frappehrms_cli import frappehrms_cli
from apps.gitlab.gitlab_cli import gitlab_cli
from apps.gumroad.gumroad_cli import gumroad_cli
from apps.mattermost.mattermost_cli import mattermost_cli
from apps.medusa.medusa_cli import medusa_cli
from apps.opencats.opencats_cli import opencats_cli
from apps.odoohr.odoohr_cli import odoohr_cli
from apps.odooinventory.odooinventory_cli import odooinventory_cli
from apps.odooproject.odooproject_cli import odooproject_cli
from apps.odoosales.odoosales_cli import odoosales_cli
from apps.onlyofficedocs.onlyofficedocs_cli import onlyofficedocs_cli
from apps.owncloud.owncloud_cli import owncloud_cli
from apps.spree.spree_cli import spree_cli
from apps.supabase.supabase_cli import supabase_cli
from apps.superset.superset_cli import superset_cli
from apps.teable.teable_cli import teable_cli


@click.group()
def cli():
    pass


if __name__ == "__main__":
    cli.add_command(akaunting_cli, name="akaunting")
    cli.add_command(chatwoot_cli, name="chatwoot")
    cli.add_command(frappecrm_cli, name="frappecrm")
    cli.add_command(frappehelpdesk_cli, name="frappehelpdesk")
    cli.add_command(frappehrms_cli, name="frappehrms")
    cli.add_command(gitlab_cli, name="gitlab")
    cli.add_command(gumroad_cli, name="gumroad")
    cli.add_command(mattermost_cli, name="mattermost")
    cli.add_command(odoohr_cli, name="odoohr")
    cli.add_command(odooinventory_cli, name="odooinventory")
    cli.add_command(odooproject_cli, name="odooproject")
    cli.add_command(odoosales_cli, name="odoosales")
    cli.add_command(owncloud_cli, name="owncloud")
    cli.add_command(spree_cli, name="spree")
    cli.add_command(supabase_cli, name="supabase")
    cli.add_command(superset_cli, name="superset")
    cli.add_command(teable_cli, name="teable")
    cli.add_command(onlyofficedocs_cli, name="onlyofficedocs")
    cli.add_command(medusa_cli, name="medusa")
    cli.add_command(opencats_cli, name="opencats")
    cli()
