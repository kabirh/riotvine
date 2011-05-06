import os
import logging
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
from types import StringType
from time import time
from mimetypes import guess_type
from uuid import uuid4
import Image
import ImageEnhance
import ImageFile

from django.core.files.uploadedfile import TemporaryUploadedFile
from django.core.files.images import get_image_dimensions

from rdutils.text import slugify


_log = logging.getLogger('photo.utils')

ImageFile.MAXBLOCK = 1024*1024


def close(image):
    """Helper function to close the file descriptor of a PIL ``Image`` object."""
    try:
        if image.fp:
            image.fp.close()
    except AttributeError:
        pass


def sharpen(image):
    """Return a sharpened copy of the image and close the original image."""
    try:
        sharpener = ImageEnhance.Sharpness(image)
        sharpened_image = sharpener.enhance(1.6)
        close(image)
        return sharpened_image
    except Exception, e:
        _log.exception(e)
        return image

def get_raw_png_image(image, optimize=True):
    """Return the raw byte contents of an instance of ``Image``."""
    try:
        fp = StringIO.StringIO()
        image.save(fp, 'PNG', optimize=optimize)
        s = fp.getvalue()
        fp.close()
        return s
    except Exception, e:
        _log.exception(e)
        return None

def get_raw_image(image, jpeg_quality=96, optimize=False):
    """Return the raw byte contents of an instance of ``Image``."""
    try:
        fp = StringIO.StringIO()
        image.save(fp, 'JPEG', quality=jpeg_quality, optimize=optimize)
        s = fp.getvalue()
        fp.close()
        return s
    except Exception, e:
        _log.exception(e)
        return None


def str_to_file(s):
    """Wrap this string into a file object and return it."""
    try:
        return StringIO.StringIO(s)
    except Exception, e:
        _log.exception(e)
        return None


def image_content_function(fn):
    """Decorate an image function to reset its content before and after use.

    `content` is an open file of type django.core.files.File.

    """
    def _wrapper(content, *args, **kwargs):
        if hasattr(content, 'reset'):
            content.reset()
        ret_val = fn(content, *args, **kwargs)
        # Reset file pointer for next use.
        if hasattr(content, 'seek') and callable(content.seek):
            content.seek(0)
        return ret_val
    return _wrapper


@image_content_function
def get_image_aspect(content):
    """Return "landscape", "portrait" or "square" based on the image aspect ratio.

    ``content`` is an open file of type django.core.files.File.

    """
    try:
        dimensions = get_image_dimensions(content)
        if not dimensions:
            return 'unknown'
        w, h = dimensions
        if w > h:
            return 'landscape'
        elif h > w:
            return 'portrait'
        else:
            return 'square'
    except Exception, e:
        _log.exception(e)
        raise


@image_content_function
def get_image_format(content):
    """Returns PIL image format (JPEG, PNG, etc.)

    ``content`` is an open file of type django.core.files.File.

    """
    try:
        image = Image.open(content)
        format = image.format
        return format
    except Exception, e:
        _log.exception(e)
        return None


def resize_in_memory(image, bounding_box, jpeg_quality=96, crop=None, crop_before_resize=False, restrict_width=False):
    """Resize image and return raw image contents."""
    try:
        fp = StringIO.StringIO()
        im = resize(image, bounding_box, out_file_path=fp, jpeg_quality=jpeg_quality, crop=crop, crop_before_resize=crop_before_resize, restrict_width=restrict_width)
        s = fp.getvalue()
        fp.close()
        close(im)
        return s
    except Exception, e:
        _log.exception(e)
        return None


def get_perfect_fit_resize_crop(target_dimensions, input_dimensions=None, input_image=None):
    """Return the resizing dimensions and crop dimensions such that after
    applying such a resize and crop, the input image will have exactly
    the ``target_dimensions``. Either ``input_dimensions`` or ``input_image`` 
    must be provided.

    The ``input_image`` is returned as the 3rd element of the returned tuple.

    """
    assert input_dimensions or input_image
    if input_dimensions is None:
        if not isinstance(input_image, Image.Image): 
            input_image = Image.open(input_image)
        input_dimensions = input_image.size
    max_w, max_h = target_dimensions
    out_ratio = float(max_w)/float(max_h)
    w, h = input_dimensions
    im_ratio = float(w)/float(h)
    if out_ratio > im_ratio:
        resize_to = (max_w, max_w*h/w)
    else:
        resize_to = (max_h*w/h, max_h)
    crop = resize_to != target_dimensions and target_dimensions or None
    return resize_to, crop, input_image


def resize(image, bounding_box, out_file_path=None, jpeg_quality=96, crop=None, crop_before_resize=False, restrict_width=False):
    """Return a copy of the image scaled down to fit within the specified ``bounding_box``.

    If ``out_path`` is given, saves the resized image to that path or file like object
    The parameter ``image`` is a PIL ``Image`` object or an image filepath.

    If ``crop_before_resize`` is True, crop the image to the aspect ratio given by ``crop``.
    Then, resize the image to the dimensions given by ``crop``. Ignore bounding_box in this case.

    """
    if not isinstance(image, Image.Image):
        image = Image.open(image)

    format = image.format or 'JPEG'

    if image.mode not in ('L', 'RGB'):
        image2 = image.convert('RGB')
        close(image)
        image = image2

    (max_w, max_h) = bounding_box
    (im_w, im_h) = image.size

    im_ratio = float(im_w)/float(im_h)
    out_ratio = float(max_w)/float(max_h)

    if crop and crop_before_resize:
        crop_w, crop_h = crop
        crop_ratio = float(crop_w)/float(crop_h)
        crop_box = None
        if im_ratio < crop_ratio:
            # Image is taller. Crop along it's height.
            cr_w = im_w
            cr_h = int(cr_w/crop_ratio)
            x1, x2 = 0, cr_w
            cr_sz = (im_h - cr_h)/2
            y1, y2 = cr_sz, cr_sz + cr_h
            crop_box = (x1, y1, x2, y2)
        elif im_ratio > crop_ratio:
            # Image is wider. Crop along it's width.
            cr_h = im_h
            cr_w = int(cr_h * crop_ratio)
            y1, y2 = 0, cr_h
            cr_sz = (im_w - cr_w)/2
            x1, x2 = cr_sz, cr_sz + cr_w
            crop_box = (x1, y1, x2, y2)
        else:
            # Image has the right aspect -- don't crop
            pass
        if crop_box:
            cropped_image = image.crop(crop_box)
            close(image)
            image = cropped_image
            bounding_box = crop
            im_w, im_h = image.size
            max_w, max_h = bounding_box
            out_ratio = float(max_w)/float(max_h)
            crop = None # Crop is already done -- disable further cropping.

    do_resize = (im_w > max_w) or (im_h > max_h)

    new_size = None
    if restrict_width:
        w = max_w
        if im_w > w:
            new_size = (w, im_h*w/im_w) # Retain aspect ratio   

    if not new_size:
        if im_ratio < out_ratio:
            h = max_h
            new_size = (im_w*h/im_h, h) # Retain aspect ratio
        else:
            w = max_w
            new_size = (w, im_h*w/im_w) # Retain aspect ratio

    if do_resize:
        resized_image = image.resize(new_size, Image.ANTIALIAS)
        close(image)
        out_image = sharpen(resized_image)
    else:
        out_image = image

    if crop:
        # Crop in the center by the size given by crop parameter
        (w, h) = out_image.size
        (crop_w, crop_h) = crop
        if w <= crop_w:
            x1, x2 = 0, w
        else:
            # center align width
            x1 = (w - crop_w)/2
            x2 = x1 + crop_w
        if h <= crop_h:
            y1, y2 = 0, h
        else:
            y1 = (h - crop_h)/2
            y2 = y1 + crop_h
        crop_box = (x1, y1, x2, y2)
        cropped_image = out_image.crop(crop_box)
        close(out_image)
        if do_resize:
            # no sharpening needed
            out_image = cropped_image
        else:
            out_image = sharpen(cropped_image)

    if out_file_path:
        if format == 'JPEG':
            out_image.save(out_file_path, 'JPEG', quality=jpeg_quality)
        else:
            out_image.save(out_file_path, format)
        if isinstance(out_file_path, StringType):
            os.utime(out_file_path, None)
            _log.debug("Saved image to %s", out_file_path)
    return out_image


def remove_model_image(model_instance, field_name, save=False):
    try:
        f = getattr(model_instance, field_name)
        f and f.delete(save=save)
    except IOError:
        pass
    except:
        pass


def create_photo_versions(sender, instance, **kwargs):
    """Create `PhotoVersion`` objects for the photo object defined by `instance`.

    A version is created for a bounding box defined by each PhotoSize instance.

    """    
    from photo.models import Photo, PhotoSize, PhotoVersion
    photo = instance
    ext = '.jpg'
    t = None
    try:
        pth = photo.image.path
    except NotImplementedError:
        from django.core.files.temp import NamedTemporaryFile
        t = NamedTemporaryFile(suffix=ext)
        ix = photo.image
        if ix.closed:
            # Reload from DB
            photo = Photo.objects.get(pk=photo.pk)
            ix = photo.image
        for d in ix.chunks(4000000):
            t.write(d)
        t.flush()
        t.seek(0)
        pth = t
    for size in PhotoSize.objects.all():
        # Create a suitable filename.
        filename = '%s-%s-%s%s' % (photo.pk, uuid4().hex[::7], slugify(size.name)[:10], ext)
        ctype = guess_type(filename)[0]
        temp_file = TemporaryUploadedFile(name=filename, content_type=ctype, size=0, charset=None)
        if t:
            t.seek(0)
        try:
            version = PhotoVersion.objects.get(photo=photo, size=size)
            remove_model_image(version, 'image')
            version.image = None
        except PhotoVersion.DoesNotExist:
            version = PhotoVersion(photo=photo, size=size)
        if size.do_crop:
            resize_to, crop_box, input_image = get_perfect_fit_resize_crop(size.bounding_box, (photo.width, photo.height))
        else:
            resize_to = size.bounding_box
            crop_box = None
        # Resize to a temporary location.
        resize(pth, resize_to, out_file_path=temp_file, crop=crop_box)
        # Save resized copy to `version` instance.
        temp_file.seek(0) # Prepare file for a re-read.
        version.image.save(name=filename, content=temp_file, save=True)
        temp_file.close()
    if t:
        t.close()

