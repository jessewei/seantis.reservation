import json
from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import rrule

from five import grok
from plone.directives import form
from plone.memoize import view
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary
from zope.schema.vocabulary import SimpleTerm
from zope import interface
from z3c.form import field
from z3c.form import button
from z3c.form.ptcompat import ViewPageTemplateFile
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from z3c.form.browser.radio import RadioFieldWidget

from seantis.reservation import _
from seantis.reservation import error
from seantis.reservation import utils
from seantis.reservation.models import Allocation
from seantis.reservation.raster import VALID_RASTER_VALUES
from seantis.reservation.form import ResourceBaseForm, extract_action_data

days = SimpleVocabulary(
        [SimpleTerm(value=rrule.MO, title=_(u'Mo')),
         SimpleTerm(value=rrule.TU, title=_(u'Tu')),
         SimpleTerm(value=rrule.WE, title=_(u'We')),
         SimpleTerm(value=rrule.TH, title=_(u'Th')),
         SimpleTerm(value=rrule.FR, title=_(u'Fr')),
         SimpleTerm(value=rrule.SA, title=_(u'Sa')),
         SimpleTerm(value=rrule.SU, title=_(u'Su')),
        ]
    )
    
recurrence = SimpleVocabulary(
        [SimpleTerm(value=False, title=_(u'Once')),
         SimpleTerm(value=True, title=_(u'Daily')),
        ]
    )

def get_date_range(allocation):
    start = datetime.combine(allocation.day, allocation.start_time)
    end = datetime.combine(allocation.day, allocation.end_time)

    # since the user can only one date with separate times it is assumed
    # that an end before a start is meant for the following day
    if end < start: end += timedelta(days=1)

    return start, end

class IAllocation(form.Schema):

    id = schema.Int(
        title=_(u'Id'),
        default=-1,
        required=False
        )

    group = schema.Text(
        title=_(u'Group'),
        default=u'',
        required=False
        )

    timeframes = schema.Text(
        title=_(u'Timeframes'),
        default=u'',
        required=False
        )

    start_time = schema.Time(
        title=_(u'Start')
        )

    end_time = schema.Time(
        title=_(u'End')
        )

    recurring = schema.Choice(
        title=_(u'Recurrence'),
        vocabulary=recurrence,
        default=False
        )

    day = schema.Date(
        title=_(u'Day'),
        )

    recurrence_start = schema.Date(
        title=_(u'From'),
        )

    recurrence_end = schema.Date(
        title=_(u'Until')
        )

    days = schema.List(
        title=_(u'Days'),
        value_type=schema.Choice(vocabulary=days),
        required=False
        )

    partly_available = schema.Bool(
        title=_(u'Partly available'),
        default=False
        )

    raster = schema.Choice(
        title=_(u'Raster'),
        values=VALID_RASTER_VALUES,
        default=30
        )

    quota = schema.Int(
        title=_(u'Quota'),
        )

    @interface.invariant
    def isValidRange(Allocation):
        start, end = get_date_range(Allocation)
        
        if abs((end - start).seconds // 60) < 5:
            raise interface.Invalid(_(u'The allocation must be at least 5 minutes long'))

    @interface.invariant
    def isValidQuota(Allocation):
        if not (1 <= Allocation.quota and Allocation.quota <= 100):
            raise interface.Invalid(_(u'Quota must be between 1 and 100'))


class AllocationForm(ResourceBaseForm):
    grok.baseclass()
    hidden_fields = ['id', 'group', 'timeframes']

    template = ViewPageTemplateFile('templates/allocate.pt')

class AllocationAddForm(AllocationForm):
    permission = 'cmf.ManagePortal'

    grok.name('allocate')
    grok.require(permission)
    
    fields = field.Fields(IAllocation)
    fields['days'].widgetFactory = CheckBoxFieldWidget
    fields['recurring'].widgetFactory = RadioFieldWidget

    label = _(u'Allocation')

    def defaults(self):        
        global days
        if self.start:
            weekday = self.start.weekday()
            daymap = dict([(d.value.weekday, d.value) for d in days])
            default_days = [daymap[weekday]]
        else:
            default_days = []
            
        recurrence_start, recurrence_end = self.default_recurrence()

        return {
            'quota': self.scheduler.quota,
            'group': u'',
            'recurrence_start': recurrence_start,
            'recurrence_end': recurrence_end,
            'timeframes': self.json_timeframes(),
            'days': default_days
        }

    def timeframes(self):
        return self.context.timeframes()

    def json_timeframes(self):
        results = []
        for frame in self.timeframes():
            results.append(
                    dict(title=frame.title, start=frame.start, end=frame.end)
                )

        dthandler = lambda obj: obj.isoformat() if isinstance(obj, date) else None
        return unicode(json.dumps(results, default=dthandler))

    def default_recurrence(self):
        start = self.start and self.start.date() or None
        end = self.end and self.end.date() or None

        if not all((start, end)):
            return None, None
        
        for frame in sorted(self.timeframes(), key=lambda f: f.start):
            if frame.start <= start and start <= frame.end:
                return (frame.start, frame.end)

        return start, end

    def get_dates(self, data):
        """ Return a list with date tuples depending on the data entered by the
        user, using rrule if requested.

        """

        start, end = get_date_range(data)

        if not data.recurring:
            return ((start, end))

        rule = rrule.rrule(
                rrule.DAILY,
                byweekday=data.days,
                dtstart=data.recurrence_start, 
                until=data.recurrence_end,
            )
    
        event = lambda d: (
                datetime.combine(d, data.start_time),
                datetime.combine(d, data.end_time)
            )
        return [event(d) for d in rule]

    @button.buttonAndHandler(_(u'Allocate'))
    @extract_action_data
    def allocate(self,data):
        dates = self.get_dates(data)

        action = lambda: self.scheduler.allocate(dates, 
                raster=data.raster,
                quota=data.quota,
                partly_available=data.partly_available
            )
        
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

class AllocationEditForm(AllocationForm):
    permission = 'cmf.ManagePortal'

    grok.name('edit-allocation')
    grok.require(permission)

    fields = field.Fields(IAllocation).select(
            'id', 'group', 'start_time', 'end_time', 'day', 'quota',
        )
    label = _(u'Edit allocation')

    @property
    def allocation(self):
        if not self.id:
            return None
        else:
            return self.context.scheduler().allocation_by_id(self.id)

    def update(self, **kwargs):
        """ Fills the defaults depending on the POST arguments given. """
        if not self.id:
            self.status = utils.translate(self.context, self.request, 
                    _(u'Invalid arguments')
                )
        else:
            allocation = self.allocation

            start, end = self.start, self.end
            if not all((start, end)):
                start = allocation.display_start
                end = allocation.display_end

            self.fields['id'].field.default = self.id
            self.fields['start_time'].field.default = start.time()
            self.fields['end_time'].field.default = end.time()
            self.fields['day'].field.default = start.date()
            self.fields['quota'].field.default = allocation.quota

        super(AllocationEditForm, self).update(**kwargs)

    @button.buttonAndHandler(_(u'Edit'))
    @extract_action_data
    def edit(self, data):

        # TODO since we can't trust the id here there should be another check
        # to make sure the user has the right to work with it. 

        scheduler = self.context.scheduler()

        start, end = get_date_range(data)
        
        args = (data.id, start, end, unicode(data.group or u''), data.quota)
        action = lambda: scheduler.move_allocation(*args)
        
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

class AllocationRemoveForm(AllocationForm):
    permission = 'cmf.ManagePortal'

    grok.name('remove-allocation')
    grok.require(permission)

    fields = field.Fields(IAllocation).select('id', 'group')
    template = ViewPageTemplateFile('templates/remove_allocation.pt')
    
    label = _(u'Remove allocations')

    hidden_fields = ['id', 'group']
    ignore_requirements = True

    @button.buttonAndHandler(_(u'Delete'))
    @extract_action_data
    def delete(self, data):

        # TODO since we can't trust the id here there should be another check
        # to make sure the user has the right to work with it. 

        assert bool(data.id) != bool(data.group), "Either id or group, not both"

        scheduler = self.scheduler
        action = lambda: scheduler.remove_allocation(id=data.id, group=data.group)
        
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

    @view.memoize
    def allocations(self):
        if self.group:
            query = self.scheduler.allocations_by_group(self.group)
            query = query.order_by(Allocation._start)
            return query.all()
        elif self.id:
            try:
                return [self.scheduler.allocation_by_id(self.id)]
            except error.NoResultFound:
                return []
        else:
            return []

    def update(self, **kwargs):
        if self.id or self.group:
            self.fields['id'].field.default = self.id
            self.fields['group'].field.default = self.group
        super(AllocationRemoveForm, self).update(**kwargs)

    @view.memoize
    def event_availability(self, allocation):
        return utils.event_availability(
                self.context,
                self.request,
                self.scheduler,
                allocation
            )

    def event_class(self, allocation):
        return self.event_availability(allocation)[1]

    def event_title(self, allocation):
        return self.event_availability(allocation)[0]