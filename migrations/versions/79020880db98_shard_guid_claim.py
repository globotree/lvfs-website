"""

Revision ID: 79020880db98
Revises: c91c4ad6768a
Create Date: 2020-01-16 16:17:58.701707

"""

# revision identifiers, used by Alembic.
revision = '79020880db98'
down_revision = 'c91c4ad6768a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('component_shard_infos', sa.Column('claim_kind', sa.Text(), nullable=True))
    op.add_column('component_shard_infos', sa.Column('claim_value', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('component_shard_infos', 'claim_value')
    op.drop_column('component_shard_infos', 'claim_kind')
