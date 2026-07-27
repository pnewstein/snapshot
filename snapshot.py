from dataclasses import dataclass, asdict
import json
from pathlib import Path

import numpy as np
from napari.layers.image._image_constants import InterpolationStr
from napari.layers import Image, Points
from napari.viewer import Viewer
from napari_scripts import get_random_viewer, get_viewer_from_file
import napari

@dataclass(slots=True)
class LayerSnapshot:
    name: str
    visable: bool
    opacity: float
    blending: str
    contrast_limits: list[float | None]
    gamma: float
    colormap: str
    projection_mode: str
    interpolation: InterpolationStr

    @classmethod
    def fromImage(cls, layer: Image):
        assert layer.source.path is not None
        return cls(
            name=layer.name,
            visable=layer.visible,
            opacity=layer.opacity,
            blending=layer.blending,
            contrast_limits=layer.contrast_limits,
            gamma=layer.gamma,
            colormap=str(layer.colormap.name),
            projection_mode=layer.projection_mode.value,
            interpolation=layer.interpolation2d,
        )

    def apply_settings(self, layer: Image):
        """
        adds an image to the viewer
        """
        layer.visible = self.visable
        layer.opacity = self.opacity
        layer.blending = self.blending
        layer.contrast_limits = self.contrast_limits
        layer.gamma = self.gamma
        layer.colormap = self.colormap
        layer.projection_mode = self.projection_mode
        layer.interpolation2d = self.interpolation


@dataclass(slots=True)
class PointsSnapshot:
    name: str
    visable: bool
    opacity: float
    blending: str
    face_color: list[list[float]]
    border_color: list[list[float]]
    border_width: list[float]
    size: list[float]
    data: list[list[float]]

    @classmethod
    def fromImage(cls, layer: Points):
        return cls(
            name=layer.name,
            visable=layer.visible,
            opacity=layer.opacity,
            blending=layer.blending,
            face_color=layer.face_color.tolist(),
            border_color=layer.border_color.tolist(),
            border_width=layer.border_width.tolist(),
            size=layer.size.tolist(),
            data=layer.data.tolist(),
        )

    def create_layer(self, viewer: Viewer) -> Points:
        """
        adds an image to the viewer
        """
        layer = viewer.add_points(self.data)
        layer.name = self.name
        layer.visible = self.visable
        layer.opacity = self.opacity
        layer.blending = self.blending
        layer.face_color = self.face_color
        layer.border_color = self.border_color
        layer.border_width = self.border_width
        layer.size = self.size
        return layer


@dataclass(slots=True)
class Snapshot2D:
    file_name: str
    scene_index: int
    z_dim: tuple[float, ...]
    order: tuple[int, ...]
    margin_left: tuple[float, ...]
    margin_right: tuple[float, ...]
    layers: list[LayerSnapshot]
    points: list[PointsSnapshot]

    def save(self, path: Path):
        """
        saves as json to path
        """
        path.write_text(json.dumps(asdict(self)))

    def take_snapshot(
        self, path: Path, top_scalebar=True, viewer: Viewer | None = None
    ):
        viewer_nnul = viewer if viewer is not None else self.get_viewer()
        viewer_nnul.scale_bar.visible = True
        if top_scalebar:
            viewer_nnul.scale_bar.position = "top_left"
        viewer_nnul.window.export_figure(str(path))
        viewer_nnul.scale_bar.visible = False
        viewer_nnul.window.export_figure(str(path.with_suffix(".nscale.png")))
        if viewer is None:
            viewer_nnul.close()

    @classmethod
    def load(cls, path: Path):
        data = json.loads(path.read_text())
        if "margin_left" not in data:
            data["margin_left"] = tuple(t / 2 for t in data["thickness"])
            data["margin_right"] = data["margin_left"]
        return cls(
            file_name=data["file_name"],
            scene_index=data["scene_index"],
            z_dim=tuple(data["z_dim"]),
            order=tuple(data["order"]),
            margin_left=tuple(data["margin_left"]),
            margin_right=tuple(data["margin_right"]),
            layers=list(LayerSnapshot(**d) for d in data["layers"]),
            points=list(PointsSnapshot(**d) for d in data["points"]),
        )

    @classmethod
    def fromViewer(cls, viewer: napari.Viewer):
        layer = next(l for l in viewer.layers if isinstance(l, Image))

        assert layer.source.path is not None
        return cls(
            file_name=layer.source.path,
            scene_index=layer.metadata["scene_index"],
            z_dim=tuple(float(p) for p in viewer.dims.point),
            order=viewer.dims.order,
            margin_left=viewer.dims.margin_left,
            margin_right=viewer.dims.margin_right,
            layers=list(
                LayerSnapshot.fromImage(l)
                for l in viewer.layers
                if isinstance(l, Image)
            ),
            points=list(
                PointsSnapshot.fromImage(l)
                for l in viewer.layers
                if isinstance(l, Points)
            ),
        )

    def get_viewer(self) -> Viewer:
        """
        gets the viewer and sets it up
        """
        if self.file_name.endswith(".json"):
            viewer = get_random_viewer(Path(self.file_name), self.scene_index)
        else:
            viewer = get_viewer_from_file(Path(self.file_name), self.scene_index)
        viewer.dims.point = self.z_dim
        viewer.dims.order = self.order
        viewer.dims.margin_left = self.margin_left
        viewer.dims.margin_right = self.margin_right
        layer_names = set(s.name for s in self.layers)
        viewer_names = set(l.name for l in viewer.layers)
        names_to_delete = viewer_names - layer_names
        for names_to_delete in names_to_delete:
            viewer.layers[names_to_delete].visible = False
        for snapshot in self.layers:
            snapshot.apply_settings(viewer.layers[snapshot.name])  # type: ignore
        for points_snap in self.points:
            points_snap.create_layer(viewer)
        return viewer


