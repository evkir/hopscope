from hopscope.targets import KNOWN_LOCAL_TARGETS, check_target


def _by_name():
    return {t.name: t for t in KNOWN_LOCAL_TARGETS}


def test_dvaa_chain_is_a_local_chain_target():
    t = _by_name()["dvaa-chain"]
    assert t.chain_hop == "manager"
    assert t.dvaa_agent == ""
    assert check_target(t.card_url) == "127.0.0.1"


def test_card_targets_carry_no_chain_hop():
    assert all(not t.chain_hop for n, t in _by_name().items() if n != "dvaa-chain")
