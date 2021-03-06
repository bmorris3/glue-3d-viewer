from __future__ import absolute_import, division, print_function

import sys
import uuid

import numpy as np

from vispy.color import Color

from glue.external.echo import CallbackProperty, add_callback
from glue.core.data import Subset
from glue.core.layer_artist import LayerArtistBase
from glue.utils import nonpartial
from glue.core.exceptions import IncompatibleAttribute
from .volume_visual import MultiVolume
from .volume_visual_legacy import MultiVolume as MultiVolumeLegacy
from .colors import get_translucent_cmap

class VolumeLayerArtist(LayerArtistBase):
    """
    A layer artist to render volumes.

    This is more complex than for other visual types, because for volumes, we
    need to manage all the volumes via a single MultiVolume visual class for
    each data viewer.
    """

    attribute = CallbackProperty()
    vmin = CallbackProperty()
    vmax = CallbackProperty()
    color = CallbackProperty()
    cmap = CallbackProperty()
    alpha = CallbackProperty()
    subset_mode = CallbackProperty()

    def __init__(self, layer, vispy_viewer):

        super(VolumeLayerArtist, self).__init__(layer)

        self.layer = layer
        self.vispy_viewer = vispy_viewer

        # We create a unique ID for this layer artist, that will be used to
        # refer to the layer artist in the MultiVolume. We have to do this
        # rather than use self.id because we can't guarantee the latter is
        # unique.
        self.id = str(uuid.uuid4())

        # We need to use MultiVolume instance to store volumes, but we should
        # only have one per canvas. Therefore, we store the MultiVolume
        # instance in the vispy viewer instance.
        if not hasattr(vispy_viewer, '_multivol'):

            # Set whether we are emulating a 3D texture. This needs to be
            # enabled as a workaround on Windows otherwise VisPy crashes.
            emulate_texture = (sys.platform == 'win32' and
                               sys.version_info[0] < 3)

            try:
                multivol = MultiVolume(threshold=0.1, emulate_texture=emulate_texture)
            except:
                multivol = MultiVolumeLegacy(threshold=0.1, emulate_texture=emulate_texture)

            self.vispy_viewer.add_data_visual(multivol)
            vispy_viewer._multivol = multivol

        self._multivol = vispy_viewer._multivol
        self._multivol.allocate(self.id)

        # Set up connections so that when any of the properties are
        # modified, we update the appropriate part of the visualization
        add_callback(self, 'attribute', nonpartial(self._update_data))
        add_callback(self, 'vmin', nonpartial(self._update_limits))
        add_callback(self, 'vmax', nonpartial(self._update_limits))
        add_callback(self, 'color', nonpartial(self._update_cmap_from_color))
        add_callback(self, 'cmap', nonpartial(self._update_cmap))
        add_callback(self, 'alpha', nonpartial(self._update_alpha))
        if isinstance(self.layer, Subset):
            add_callback(self, 'subset_mode', nonpartial(self._update_data))

    @property
    def visual(self):
        return self._multivol

    @property
    def bbox(self):
        return (-0.5, self.layer.shape[2] - 0.5,
                -0.5, self.layer.shape[1] - 0.5,
                -0.5, self.layer.shape[0] - 0.5)

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        self._visible = value
        self._update_visibility()

    def redraw(self):
        """
        Redraw the Vispy canvas
        """
        self.vispy_viewer.canvas.update()

    def clear(self):
        """
        Remove the layer artist from the visualization
        """
        self._multivol.deallocate(self.id)

    def update(self):
        """
        Update the visualization to reflect the underlying data
        """
        self.redraw()
        self._changed = False

    def _update_cmap_from_color(self):
        cmap = get_translucent_cmap(*Color(self.color).rgb)
        self._multivol.set_cmap(self.id, cmap)
        self.redraw()

    def _update_cmap(self):
        self._multivol.set_cmap(self.id, self.cmap)
        self.redraw()

    def _update_limits(self):
        self._multivol.set_clim(self.id, (self.vmin, self.vmax))
        self.redraw()

    def _update_alpha(self):
        self._multivol.set_weight(self.id, self.alpha)
        self.redraw()

    def _update_data(self):
        if isinstance(self.layer, Subset):
            try:    
                mask = self.layer.to_mask()
            except IncompatibleAttribute:
                mask = np.zeros(self.layer.data.shape, dtype=bool)
            if self.subset_mode == 'outline':
                data = mask.astype(float)
            else:
                data = self.layer.data[self.attribute] * mask
        else:
            data = self.layer[self.attribute]
        self._multivol.set_data(self.id, data)
        self.redraw()

    def _update_visibility(self):
        if self.visible:
            self._multivol.enable(self.id)
        else:
            self._multivol.disable(self.id)
        self.redraw()
