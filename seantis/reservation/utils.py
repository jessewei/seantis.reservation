import re

from Acquisition import aq_inner
from zope.component import getMultiAdapter
from zope import i18n
from zope import interface
from Products.CMFCore.utils import getToolByName
from z3c.form.interfaces import ActionExecutionError

from seantis.reservation import _

def get_current_language(context, request):
    """Returns the current language"""
    context = aq_inner(context)
    portal_state = getMultiAdapter((context, request), name=u'plone_portal_state')
    return portal_state.language()

def translate(context, request, text):
    lang = get_current_language(context, request)
    return i18n.translate(text, target_language=lang)

def form_error(msg):
    raise ActionExecutionError(interface.Invalid(msg))

def is_uuid(text):
    regex = re.compile(
            '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'
        )

    return re.match(regex, unicode(text))

def get_resource_by_uuid(context, uuid):
    catalog = getToolByName(context, 'portal_catalog')
    results = catalog(UID=uuid)
    return len(results) == 1 and results[0] or None

def event_color(occupation_rate):
    # TODO move colors to css
    if occupation_rate == 100:
        return '#a1291e' #redish
    elif occupation_rate == 0:
        return '#379a00' #greenish
    else:
        return '#e99623' #orangeish

def event_title(context, request, occupation_rate):
    if occupation_rate == 100:
        return translate(context, request, _(u'Occupied'))
    elif occupation_rate == 0:
        return translate(context, request, _(u'Free'))
    else:
        return translate(context, request, _(u'%i%% Occupied')) % occupation_rate