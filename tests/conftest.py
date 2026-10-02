"""Synthetic captures shared by the tests. Each is rendered once per test session."""

import pytest

from floorplan.io.stray import read_stray
from floorplan.pipeline import PipelineConfig, run
from floorplan.synth.render import make_capture
from floorplan.synth.scene import SCENES


def _capture(tmp_path_factory, scene, **kwargs):
    folder = tmp_path_factory.mktemp(scene)
    make_capture(scene, folder, **kwargs)
    return folder


@pytest.fixture(scope="session")
def box_room_folder(tmp_path_factory):
    return _capture(tmp_path_factory, "box_room")


@pytest.fixture(scope="session")
def box_room_plan(box_room_folder):
    return run(read_stray(box_room_folder), PipelineConfig())


@pytest.fixture(scope="session")
def furnished_room_plan(tmp_path_factory):
    folder = _capture(tmp_path_factory, "furnished_room")
    return run(read_stray(folder), PipelineConfig())


@pytest.fixture(scope="session")
def flat_folder(tmp_path_factory):
    return _capture(tmp_path_factory, "flat")


@pytest.fixture(scope="session")
def flat_plan(flat_folder):
    return run(read_stray(flat_folder), PipelineConfig())


@pytest.fixture(scope="session")
def truth():
    return {name: build().ground_truth() for name, build in SCENES.items()}
