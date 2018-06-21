from __future__ import print_function

from django.http import Http404, HttpResponse,\
	HttpResponseBadRequest, JsonResponse
from collections import OrderedDict

import omero
from omero.rtypes import wrap
from omeroweb.webclient.decorators import login_required, render_response
from omeroweb.http import HttpJavascriptResponse,\
    HttpJavascriptResponseServerError

from omeroweb.webgateway.marshal import imageMarshal

from nicatkcl_gallery import settings

import json
import re
import collections


def list_from_string(expression, str):
    pattern = re.compile(expression)
    split = str.split('\n')

    words = []
    for l in split:
        for w in re.findall(pattern, l):
            words.append(w)
    return words


def dict_from_string(str):
    key_expression = r"\{([\sA-Za-z0-9_()/]+)\}"
    keys = list_from_string(key_expression, str)
    if not keys:
        key_expression = r"([\sA-Za-z0-9_()/]+)\:"
        keys = list_from_string(key_expression, str)

    val_expression = r"\:([\sA-Za-z0-9_/-]+)"
    vals = list_from_string(val_expression, str)

    if len(keys) == len(vals):
        dictionary = OrderedDict()
        for i in range(len(keys)):
            dictionary[keys[i]] = vals[i]

    return dictionary


@login_required()
@render_response()
def index(request, conn=None, **kwargs):
    """
    Home page shows a list of Projects from all of our groups
    """
    print(settings)
    myGroups = list(conn.getGroupsMemberOf())

    # Need a custom query to get 1 (random) image per Project
    queryService = conn.getQueryService()
    params = omero.sys.ParametersI()
    params.theFilter = omero.sys.Filter()
    params.theFilter.limit = wrap(1)

    query = "select count(obj.id) from %s as obj"

    groups = []
    for g in myGroups:
        conn.SERVICE_OPTS.setOmeroGroup(g.id)
        projects = []
        images = list(conn.getObjects("Image", params=params))
        if len(images) == 0:
            continue        # Don't display empty groups
        pCount = queryService.projection(
            query % 'Project', None, conn.SERVICE_OPTS
        )
        dCount = queryService.projection(
            query % 'Dataset', None, conn.SERVICE_OPTS
        )
        iCount = queryService.projection(
            query % 'Image', None, conn.SERVICE_OPTS
        )

        groups.append({
            'id': g.getId(),
            'name': g.getName(),
            'description': g.getDescription(),
            'projectCount': pCount[0][0]._val,
            'datasetCount': dCount[0][0]._val,
            'imageCount': iCount[0][0]._val,
            'image': len(images) > 0 and images[0] or None
        })

    context = {'template': "gallery/index.html"}
    context['groups'] = groups

    return context


@login_required()
@render_response()
def showcase(request, conn=None, **kwargs):

    groupId = 4  # settings.SHOWCASE_GROUP['groupId']
    conn.SERVICE_OPTS.setOmeroGroup(groupId)

    s = conn.groupSummary(groupId)
    group_owners = s["leaders"]
    group_members = s["colleagues"]
    group = conn.getObject("ExperimenterGroup", groupId)

    # Get NEW user_id, OR current user_id from session OR 'All Members' (-1)
    if request.GET:
        user_id = request.GET['user_id']
    else:
        user_id = request.session.get('user_id', -1)
    userIds = [u.id for u in group_owners]
    userIds.extend([u.id for u in group_members])
    user_id = int(user_id)

    # Check user is in group
    if user_id not in userIds and user_id is not -1:
        user_id = -1

    # save it to session
    request.session['user_id'] = int(user_id)
    request.session.modified = True

    queryService = conn.getQueryService()
    params = omero.sys.ParametersI()
    params.theFilter = omero.sys.Filter()
    params.theFilter.limit = wrap(1)
    # params.map = {}
    query = (
        "select i from Image as i"
        " left outer join i.datasetLinks as dl join dl.parent as dataset"
        " left outer join dataset.projectLinks as pl join pl.parent as project"
        " where project.id = :pid"
    )

    paramAll = omero.sys.ParametersI()
    countImages = (
        "select count(i), count(distinct dataset) from Image as i"
        " left outer join i.datasetLinks as dl join dl.parent as dataset"
        " left outer join dataset.projectLinks as pl join pl.parent as project"
        " where project.id = :pid"
    )

    if user_id == -1:
        user_id = None
    projects = []
    # Will be from active group, owned by user_id (as perms allow)
    for p in conn.listProjects(eid=user_id):
        pdata = {'id': p.getId(), 'name': p.getName()}
        pdata['description'] = p.getDescription()
        pdata['owner'] = p.getDetails().getOwner().getOmeName()
        # Look-up a single image
        params.addLong('pid', p.id)
        img = queryService.findByQuery(query, params, conn.SERVICE_OPTS)
        if img is None:
            continue    # Ignore projects with no images
        pdata['image'] = {'id': img.id.val, 'name': img.name.val}
        paramAll.addLong('pid', p.id)

        imageCount = queryService.projection(
            countImages, paramAll, conn.SERVICE_OPTS
        )

        pdata['imageCount'] = imageCount[0][0].val
        pdata['datasetCount'] = imageCount[0][1].val
        projects.append(pdata)

    query = (
        "select i from Image as i"
        " left outer join i.datasetLinks as dl join dl.parent as dataset"
        " where dataset.id = :did"
    )

    countImages = (
        "select count(i) from Image as i"
        " left outer join i.datasetLinks as dl join dl.parent as dataset"
        " where dataset.id = :did"
    )

    datasets = []
    for d in conn.listOrphans("Dataset", eid=user_id):
        ddata = {'id': d.getId(), 'name': d.getName()}
        ddata['description'] = d.getDescription()
        ddata['owner'] = d.getDetails().getOwner().getOmeName()
        # Look-up a single image
        # params.map['did'] = wrap(d.id)
        params.addLong('did', d.id)
        img = queryService.findByQuery(query, params, conn.SERVICE_OPTS)
        if img is None:
            continue    # ignore datasets with no images
        ddata['image'] = {'id': img.id.val, 'name': img.name.val}
        paramAll.addLong('did', d.id)
        imageCount = queryService.projection(
            countImages, paramAll, conn.SERVICE_OPTS
        )
        ddata['imageCount'] = imageCount[0][0].val
        datasets.append(ddata)

    context = {'template': "gallery/show_group.html"}
    context['group'] = group
    context['group_owners'] = group_owners
    context['group_members'] = group_members
    context['projects'] = projects
    context['datasets'] = datasets

    return context


@login_required()
@render_response()
def show_group(request, groupId, conn=None, **kwargs):
    conn.SERVICE_OPTS.setOmeroGroup(groupId)

    s = conn.groupSummary(groupId)
    group_owners = s["leaders"]
    group_members = s["colleagues"]
    group = conn.getObject("ExperimenterGroup", groupId)

    # Get NEW user_id, OR current user_id from session OR 'All Members' (-1)
    user_id = request.REQUEST.get(
        'user_id', request.session.get('user_id', -1)
    )

    userIds = [u.id for u in group_owners]
    userIds.extend([u.id for u in group_members])
    user_id = int(user_id)
    # Check user is in group
    if user_id not in userIds and user_id is not -1:
        user_id = -1
    # save it to session
    request.session['user_id'] = int(user_id)
    request.session.modified = True

    queryService = conn.getQueryService()
    params = omero.sys.ParametersI()
    params.theFilter = omero.sys.Filter()
    params.theFilter.limit = wrap(1)
    # params.map = {}
    query = (
        "select i from Image as i"
        " left outer join i.datasetLinks as dl join dl.parent as dataset"
        " left outer join dataset.projectLinks as pl join pl.parent as project"
        " where project.id = :pid"
    )

    paramAll = omero.sys.ParametersI()
    countImages = (
        "select count(i), count(distinct dataset) from Image as i"
        " left outer join i.datasetLinks as dl join dl.parent as dataset"
        " left outer join dataset.projectLinks as pl join pl.parent as project"
        " where project.id = :pid"
    )

    if user_id == -1:
        user_id = None
    projects = []
    # Will be from active group, owned by user_id (as perms allow)
    for p in conn.listProjects(eid=user_id):
        pdata = {'id': p.getId(), 'name': p.getName()}
        pdata['description'] = p.getDescription()
        pdata['owner'] = p.getDetails().getOwner().getOmeName()
        # Look-up a single image
        params.addLong('pid', p.id)
        img = queryService.findByQuery(query, params, conn.SERVICE_OPTS)
        if img is None:
            continue    # Ignore projects with no images

        pdata['image'] = {'id': img.id.val, 'name': img.name.val}
        paramAll.addLong('pid', p.id)
        imageCount = queryService.projection(
            countImages, paramAll, conn.SERVICE_OPTS
        )
        pdata['imageCount'] = imageCount[0][0].val
        pdata['datasetCount'] = imageCount[0][1].val
        projects.append(pdata)

    query = (
        "select i from Image as i"
        " left outer join i.datasetLinks as dl join dl.parent as dataset"
        " where dataset.id = :did"
    )

    countImages = (
        "select count(i) from Image as i"
        " left outer join i.datasetLinks as dl join dl.parent as dataset"
        " where dataset.id = :did"
    )

    datasets = []
    for d in conn.listOrphans("Dataset", eid=user_id):
        ddata = {'id': d.getId(), 'name': d.getName()}
        ddata['description'] = d.getDescription()
        ddata['owner'] = d.getDetails().getOwner().getOmeName()
        # Look-up a single image
        # params.map['did'] = wrap(d.id)
        params.addLong('did', d.id)
        img = queryService.findByQuery(query, params, conn.SERVICE_OPTS)
        if img is None:
            continue    # ignore datasets with no images
        ddata['image'] = {'id': img.id.val, 'name': img.name.val}
        paramAll.addLong('did', d.id)
        imageCount = queryService.projection(
            countImages, paramAll, conn.SERVICE_OPTS
        )
        ddata['imageCount'] = imageCount[0][0].val
        datasets.append(ddata)

    context = {'template': "gallery/show_group.html"}
    context['group'] = group
    context['group_owners'] = group_owners
    context['group_members'] = group_members
    context['projects'] = projects
    context['datasets'] = datasets

    return context


@login_required()
@render_response()
def show_project(request, projectId, conn=None, **kwargs):
    """
    Show a project
    """

    project = conn.getObject("Project", projectId)

    if project is None:
        raise Http404

    # Set a limit to grab 5 images from each Dataset
    params = omero.sys.Parameters()
    params.theFilter = omero.sys.Filter()
    params.theFilter.limit = wrap(5)

    datasets = []
    for ds in project.listChildren():
        # want to display 5 images from each dataset
        images = ds.listChildren(params=params)
        datasets.append({
            "id": ds.getId(),
            "name": ds.getName(),
            "description": ds.getDescription(),
            "images": images
        })

    context = {'template': "gallery/show_project.html"}
    context['project'] = project
    context['datasets'] = datasets

    return context


@login_required()
@render_response()
def show_dataset(request, datasetId, conn=None, **kwargs):
    """
    Show a dataset
    """

    dataset = conn.getObject("Dataset", datasetId)

    if dataset is None:
        raise Http404

    context = {'template': "gallery/show_dataset.html"}
    context['dataset'] = dataset

    return context


@login_required()
@render_response()
def show_image(request, imageId, conn=None, **kwargs):
    """
    Show an image
    """

    image = conn.getObject("Image", imageId)

    if image is None:
        raise Http404

    tags = []
    for ann in image.listAnnotations():
        if isinstance(ann, omero.gateway.TagAnnotationWrapper):
            tags.append(ann)

    context = {'template': "gallery/show_image.html"}
    context['image'] = image
    context['tags'] = tags

    return context


@login_required()
@render_response()
def image_info(request, conn=None, **kwargs):
    """
    Show image information
    """

    if request.is_ajax():
        print(request.POST)
        imageId = request.POST['imageId']

        image = conn.getObject("Image", imageId)

        if image is None:
            message = 'image not found'
            rv = {'success': False, 'message': message}
            error = json.dumps(rv)
            return HttpResponseBadRequest(
                error, content_type='application/json'
            )

        metadata = image.loadOriginalMetadata()
        global_metadata = metadata[1]

        camera = (
            [
                v[1] for i, v in enumerate(global_metadata)
                if v[0] == 'Camera Type #1'
            ][0]
        )

        channel_names = []
        for c in image.getChannels():
            channel_names.append(c.getLabel())

        pixelSizeX = 'Not defined'
        if image.getPixelSizeX():
            pixelSizeX = image.getPixelSizeX()

        pixelSizeY = 'Not defined'
        if image.getPixelSizeY():
            pixelSizeY = image.getPixelSizeY()

        pixelSizeZ = 'Not defined'
        if image.getPixelSizeZ():
            pixelSizeZ = image.getPixelSizeZ()

        rv = {
            'image_name': image.getName(),
            'sizeX': image.getSizeX(),
            'sizeY': image.getSizeY(),
            'sizeZ': image.getSizeZ(),
            'sizeT': image.getSizeT(),
            'channel_names': channel_names,
            'pixels_type': image.getPixelsType(),
            'pixelSizeX': pixelSizeX,
            'pixelSizeY': pixelSizeY,
            'pixelSizeZ': pixelSizeZ,
            'camera': camera
        }

        data = json.dumps(rv)
        return HttpResponse(data, content_type='application/json')
    else:
        # just in case javascript is turned off
        # note to self - this needs to be done through a form submit

        imageId = request.POST['imageId']

        image = conn.getObject("Image", imageId)
        context = {'template': "gallery/image_info.html"}
        context['image'] = image

        return context


@login_required()
@render_response()
def image_infolink(request, imageId, conn=None, **kwargs):
    """
    Show image information
    """
    if request.is_ajax():
        print(request.POST)

        image = conn.getObject("Image", imageId)
        print("Image ID: {}".format(imageId))

        if image is None:
            message = 'image not found'
            rv = {'success': False, 'message': message}
            error = json.dumps(rv)
            return HttpResponseBadRequest(
                error, content_type='application/json'
            )

        metadata = image.loadOriginalMetadata()
        global_metadata = metadata[1]
        sSpec = (
            [
                v[1] for i, v in enumerate(global_metadata)
                if v[0] == 'sSpecSettings'
            ]
        )

        sSpecSettings = dict_from_string(sSpec[0])

        camera_list = (
            [
                v[1] for i, v in enumerate(global_metadata)
                if v[0] == 'Camera Type #1'
            ]
        )

        camera = 'Not defined'
        if camera_list:
            camera = camera_list[0]

        channel_names = []
        for c in image.getChannels():
            channel_names.append(c.getLabel())

        pixelSizeX = 'Not defined'
        if image.getPixelSizeX():
            pixelSizeX = image.getPixelSizeX()
            pixelSizeX = "{0:.3f}".format(pixelSizeX)

        pixelSizeY = 'Not defined'
        if image.getPixelSizeY():
            pixelSizeY = image.getPixelSizeY()
            pixelSizeY = "{0:.3f}".format(pixelSizeY)

        pixelSizeZ = 'Not defined'
        if image.getPixelSizeZ():
            pixelSizeZ = image.getPixelSizeZ()
            pixelSizeZ = "{0:.3f}".format(pixelSizeZ)

        basic = {
            'Image_name': image.getName(),
            'size X': image.getSizeX(),
            'size Y': image.getSizeY(),
            'size Z': image.getSizeZ(),
            'size T': image.getSizeT(),
            'Channel names': channel_names,
            'Pixels type': image.getPixelsType(),
            'Pixel size X (um)': pixelSizeX,
            'Pixel size Y (um)': pixelSizeY,
            'Pixel size Z (um)': pixelSizeZ,
            'Camera': camera
        }
        rv = basic.copy()
        rv.update(sSpecSettings)
        data = json.dumps(collections.OrderedDict(sorted(rv.items())))
        return HttpResponse(data, content_type='application/json')
    else:
        # just in case javascript is turned off
        # note to self - this needs to be done through a form submit

        # mageId = request.POST['imageId']

        image = conn.getObject("Image", imageId)
        context = {'template': "gallery/image_info.html"}
        context['image'] = image

        return context


def jsonp(f):
    """
    Decorator for adding connection debugging and returning function result as
    json, depending on values in kwargs
    @param f:       The function to wrap
    @return:        The wrapped function, which will return json
    """

    def wrap(request, *args, **kwargs):

        try:
            server_id = kwargs.get('server_id', None)
            if server_id is None and request.session.get('connector'):
                server_id = request.session['connector'].server_id
            kwargs['server_id'] = server_id
            rv = f(request, *args, **kwargs)
            if kwargs.get('_raw', False):
                return rv
            if isinstance(rv, HttpResponse):
                return rv
            c = request.GET.get('callback', None)
            if c is not None and not kwargs.get('_internal', False):
                rv = json.dumps(rv)
                rv = '%s(%s)' % (c, rv)
                # mimetype for JSONP is application/javascript
                return HttpJavascriptResponse(rv)
            if kwargs.get('_internal', False):
                return rv
            # mimetype for JSON is application/json
            # NB: To support old api E.g. /get_rois_json/
            # We need to support lists
            safe = type(rv) is dict
            return JsonResponse(rv, safe=safe)
        except Exception, ex:
            # Default status is 500 'server error'
            # But we try to handle all 'expected' errors appropriately
            # TODO: handle omero.ConcurrencyException
            status = 500
            if isinstance(ex, omero.SecurityViolation):
                status = 403
            elif isinstance(ex, omero.ApiUsageException):
                status = 400

            if kwargs.get('_raw', False) or kwargs.get('_internal', False):
                raise
            return JsonResponse(
                {"message": str(ex)},
                status=status)
    wrap.func_name = f.func_name
    return wrap


@login_required()
@jsonp
def imageData_json(request, conn=None, _internal=False, **kwargs):
    """
    Get a dict with image information
    TODO: cache
    @param request:     http request
    @param conn:        L{omero.gateway.BlitzGateway}
    @param _internal:   TODO: ?
    @return:            Dict
    """

    iid = kwargs['iid']
    key = kwargs.get('key', None)
    image = conn.getObject("Image", iid)
    if image is None:
        return HttpJavascriptResponseServerError('""')
    metadata = image.loadOriginalMetadata()
    global_metadata = metadata[1]
    sSpec = (
        [
            v[1] for i, v in enumerate(global_metadata)
            if v[0] == 'sSpecSettings'
        ]
    )

    sSpecSettings = dict_from_string(sSpec[0])
    print(sSpecSettings)
    camera_list = (
        [
            v[1] for i, v in enumerate(global_metadata)
            if v[0] == 'Camera Type #1'
        ]
    )

    camera = 'Not defined'
    if camera_list:
        camera = camera_list[0]

    channel_names = []
    for c in image.getChannels():
        channel_names.append(c.getLabel())

    pixelSizeX = 'Not defined'
    if image.getPixelSizeX():
        pixelSizeX = image.getPixelSizeX()
        pixelSizeX = "{0:.3f}".format(pixelSizeX)

    pixelSizeY = 'Not defined'
    if image.getPixelSizeY():
        pixelSizeY = image.getPixelSizeY()
        pixelSizeY = "{0:.3f}".format(pixelSizeY)

    pixelSizeZ = 'Not defined'
    if image.getPixelSizeZ():
        pixelSizeZ = image.getPixelSizeZ()
        pixelSizeZ = "{0:.3f}".format(pixelSizeZ)

    basic = OrderedDict(
        [
            ('Image_name', image.getName()),
            ('size X', image.getSizeX()),
            ('size Y', image.getSizeY()),
            ('size Z', image.getSizeZ()),
            ('size T', image.getSizeT()),
            ('Channel names', channel_names),
            ('Pixels type', image.getPixelsType()),
            ('Pixel size X (um)', pixelSizeX),
            ('Pixel size Y (um)', pixelSizeY),
            ('Pixel size Z (um)', pixelSizeZ),
        ]
    )
    print(basic)
    # rv = basic.copy()
    rv = OrderedDict(basic.items() + sSpecSettings.items())

    print(rv)
    # rv.update(sSpecSettings)
    if key is not None and rv is not None:
        # rv_filtered = basic.copy()
        filtered = OrderedDict([
            (k, sSpecSettings.get(k, None)) for k in key.split('.')
        ])
        rv_filtered = OrderedDict(basic.items() + filtered.items())
        return rv_filtered
    return rv
