from dataclasses import dataclass
from datetime import datetime

from greyjack.score_calculation.greynet.greynet_fact import *
from greyjack.score_calculation.greynet.builder import ConstraintBuilder, Collectors
from greyjack.score_calculation.greynet.common.joiner_type import JoinerType
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from datetime import datetime, timedelta

@greynet_fact
@dataclass()
class UserLogin:
    user_id: str
    timestamp: datetime

@greynet_fact
@dataclass()
class UserBan:
    user_id: str
    banned_at: datetime

builder = ConstraintBuilder("bloom_example", score_class=SimpleScore)

@builder.constraint("login_not_banned")
def login_not_banned():
    # Start from UserLogin facts
    login_stream = builder.for_each(UserLogin)
    # Join with UserBan facts, using NOT_EQUAL on user_id
    # This will use the CountingBloomFilter under the hood
    not_banned_stream = login_stream.join(
        builder.for_each(UserBan),
        JoinerType.NOT_EQUAL,
        left_key_func=lambda login: login.user_id,
        right_key_func=lambda ban: ban.user_id
    )
    # For every login where there is NO ban with the same user_id, penalize (or reward)
    return not_banned_stream.penalize_simple(lambda login, ban: -1.0)

session = builder.build()

# Insert facts
logins = [
    UserLogin(user_id="alice", timestamp=datetime.now()),
    UserLogin(user_id="bob", timestamp=datetime.now()),
    UserLogin(user_id="carol", timestamp=datetime.now()),
]

bans = [
    UserBan(user_id="bob", banned_at=datetime.now() - timedelta(days=1)),
]

for login in logins:
    session.insert(login)
for ban in bans:
    session.insert(ban)

# Get the score (should only penalize logins by users NOT banned)
score = session.get_score()
print("Total score:", score.simple_value)

# Get detailed constraint matches
matches = session.get_constraint_matches()
print("Constraint matches:", matches)
