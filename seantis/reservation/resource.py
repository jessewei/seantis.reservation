import json
import time

from datetime import datetime
from datetime import timedelta

from five import grok
from plone.directives import form
from plone.dexterity.content import Container
from plone.uuid.interfaces import IUUID
from zope import schema
from zope import interface

from seantis.reservation import utils
from seantis.reservation import Scheduler
from seantis.reservation import _


class IResourceBase(form.Schema):

    title = schema.TextLine(
            title=_(u'Name')
        )

    description = schema.Text(
            title=_(u'Description'),
            required=False
        )

    first_hour = schema.Int(
            title=_(u'First hour of the day'),
            default=0
        )

    last_hour = schema.Int(
            title=_(u'Last hour of the day'),
            default=24
        )

    @interface.invariant
    def isValidFirstLastHour(Resource):
        in_valid_range = lambda h: 0 <= h and h <= 24
        first_hour, last_hour = Resource.first_hour, Resource.last_hour
        
        if not in_valid_range(first_hour):
            raise interface.Invalid(_(u'Invalid first hour'))

        if not in_valid_range(last_hour):
            raise interface.Invalid(_(u'Invalid last hour'))

        if last_hour <= first_hour:
            raise interface.Invalid(
                    _(u'First hour must be smaller than last hour')
                )
                     

class IResource(IResourceBase):
    pass


class Resource(Container):

    @property
    def uuid(self):
        return IUUID(self)

    @property
    def scheduler(self):
        return Scheduler(self.uuid)

class View(grok.View):
    grok.context(IResourceBase)
    grok.require('zope2.View')
    
    template = grok.PageTemplateFile('templates/resource.pt')

    calendar_id = 'seantis-reservation-calendar'

    @property
    def calendar_options(self):
        template = """
        <script type="text/javascript">
            if (!this.seantis) this.seantis = {};
            if (!this.seantis) this.seantis.calendar = {};
            
            seantis.calendar.id = '#%s';
            seantis.calendar.options = %s;
            seantis.calendar.allocateurl = '%s';
        </script>
        """

        contexturl = self.context.absolute_url_path()
        allocateurl = contexturl + '/allocate'
        eventurl = contexturl + '/slots'

        options = {}
        options['events'] = eventurl
        options['minTime'] = self.context.first_hour
        options['maxTime'] = self.context.last_hour

        return template % (self.calendar_id, options, allocateurl)


class Slots(grok.View):
    grok.context(IResourceBase)
    grok.require('zope2.View')
    grok.name('slots')

    @property
    def range(self):
        # TODO make sure that fullcalendar reports the time in utc

        start = self.request.get('start', None)
        end = self.request.get('end', None)
        
        if not all((start, end)):
            return None, None

        start = datetime.fromtimestamp(float(start))
        end = datetime.fromtimestamp(float(end))

        return start, end

    def render(self, **kwargs):
        slots = []
        start, end = self.range

        if not all((start, end)):
            return json.dumps(slots)

        scheduler = self.context.scheduler
        translate = lambda txt: utils.translate(self.context, self.request, txt)
        baseurl = self.context.absolute_url_path() + '/reserve?start=%s&end=%s'
        editurl = self.context.absolute_url_path() + '/allocation_edit?id=%i'

        for allocation in scheduler.allocations_in_range(start, end):
            start, end = allocation.start, allocation.end
            rate = int(allocation.occupation_rate)

            # TODO move colors to css

            if rate == 100:
                title = translate(_(u'Occupied'))
                color = '#a1291e' #redish
            elif rate == 0:
                title = translate(_(u'Free'))
                color = '#379a00' #greenish
            else:
                title = translate(_(u'%i%% Occupied')) % rate
                color = '#e99623' #orangeish

            # add the microsecond which is substracted on creation
            # for nicer displaying
            end += timedelta(microseconds=1)
        
            url = baseurl % (
                time.mktime(start.timetuple()),
                time.mktime(end.timetuple()),
                )

            edit = editurl % (
                allocation.id
                )
            
            slots.append(
                dict(
                    start=start.isoformat(),
                    end=end.isoformat(),
                    title=title,
                    allDay=False,
                    backgroundColor=color,
                    borderColor=color,
                    url=url,
                    editurl=edit,
                    allocation = allocation.id
                )
            )
            
        return json.dumps(slots)