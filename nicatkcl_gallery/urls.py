from django.conf.urls import *

from . import views

urlpatterns = patterns(

    'django.views.generic.simple',

    # index 'home page' of the webgallery app
    # url( r'^$', views.index, name='webgallery_index' ),
    url(
        r'^$',
        views.showcase,
        name='nic_at_kcl_gallery_showcase'
    ),

    # group view
    url(
        r'show_group/(?P<groupId>[0-9]+)/$',
        views.show_group,
        name='nic_at_kcl_gallery_show_group'
    ),

    # project view
    url(
        r'show_project/(?P<projectId>[0-9]+)/$',
        views.show_project,
        name='nic_at_kcl_gallery_show_project'
    ),

    # dataset view
    url(
        r'show_dataset/(?P<datasetId>[0-9]+)/$',
        views.show_dataset,
        name='nic_at_kcl_gallery_show_dataset'
    ),

    # use the same dataset view, with a different
    # template that only shows thumbnails
    url(
        r'dataset_thumbs/(?P<datasetId>[0-9]+)/$',
        views.show_dataset,
        {'template': 'gallery/dataset_thumbs.html'},
        name='nic_at_kcl_gallery_dataset_thumbs'
    ),

    # image view
    url(
        r'show_image/(?P<imageId>[0-9]+)/$',
        views.show_image,
        name='nic_at_kcl_gallery_show_image'
    ),

    url(
        r'image_info$',
        views.image_info,
        name='nic_at_kcl_gallery_image_info'
    ),

    url(
        r'image_infolink/(?P<imageId>[0-9]+)/$',
        views.image_infolink,
        name='nic_at_kcl_gallery_image_infolink'
    ),


    url(
        r'^imgData/(?P<iid>[0-9]+)/(?:(?P<key>[^/]+)/)?$',
        views.imageData_json,
        name='nic_at_kcl_gallery_imageData_json'

    ),

)
