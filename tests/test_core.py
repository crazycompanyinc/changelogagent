from changelogagent.core.models import EventType, ProjectEvent


def test_event_serialization_round_trip():
    event = ProjectEvent(event_type="commit", source="alice", target="api", title="Change API")
    restored = ProjectEvent.from_dict(event.to_dict())
    assert restored.id == event.id
    assert restored.event_type == EventType.COMMIT


def test_store_persists_events(store):
    event = ProjectEvent(event_type="incident", source="ops", target="api", title="Errors")
    store.add_event(event)
    events = store.list_events()
    assert [item.id for item in events] == [event.id]


def test_store_filters_target(store):
    store.add_event(ProjectEvent(event_type="commit", source="a", target="api", title="A"))
    store.add_event(ProjectEvent(event_type="commit", source="b", target="web", title="B"))
    assert len(store.list_events(target="api")) == 1
