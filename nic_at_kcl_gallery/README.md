Gallery
=======

This app is a heavily modified version of [OMERO.gallery](https://github.com/ome/gallery "OMERO.gallery") specifically for use by the [Nikon Imaging Centre @ King's College London](http://nic.kcl.ac.uk "NIC@ King's College London"). No installation instructions are provided here - you should fork the original repo if you interested in a gallery app for your OMERO installation.

Just like the original version of the app, the data is stored inside an OMERO server but here the index page displays data within one public group called 'Showcase'. The group ID is assigned through the use of of 'CUSTOM_SETTINGS_MAPPINGS' as shown below. The datasets within this group are arranged by microscope. I have added a [Bootstrap](http://getbootstrap.com/ "Bootstrap") modal which displays the metadata for each image.


```python
import json
CUSTOM_SETTINGS_MAPPINGS = {
    "omero.web.gallery.showcase_group": ["SHOWCASE_GROUP", '{"groupId": "val"}', json.loads, None]
}
```
Then load the group ID in views.py:

```python
groupId = settings.SHOWCASE_GROUP['groupId']
```