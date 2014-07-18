from datetime import date, datetime, time
from five import grok
from plone import api
from plone.autoform.form import AutoExtensibleForm
from plone.directives import form
from plone.supermodel import model
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from zope import schema

from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.utils import cached_property
from seantis.reservation.form import BaseForm
from seantis.reservation.resource import YourReservationsViewlet
from seantis.reservation.interfaces import IResourceBase, days as weekdays


class ISearchAndReserveForm(model.Schema):
    """ Search form for search & reserve view. """

    form.mode(timeframes='hidden')
    timeframes = schema.Text(
        title=_(u'Timeframes'),
        default=u'',
        required=False
    )

    recurrence_start = schema.Date(
        title=_(u"Start date"),
        required=True
    )

    recurrence_end = schema.Date(
        title=_(u"End date"),
        required=True
    )

    whole_day = schema.Bool(
        title=_(u"Whole day"),
        required=False,
        default=False
    )

    start_time = schema.Time(
        title=_(u"Start time"),
        required=False
    )

    end_time = schema.Time(
        title=_(u"End time"),
        required=False
    )

    form.widget(days=CheckBoxFieldWidget)
    days = schema.List(
        title=_(u"Days"),
        value_type=schema.Choice(vocabulary=weekdays),
        required=False
    )

    minspots = schema.Int(
        title=_(u"Spots"),
        required=False
    )

    available_only = schema.Bool(
        title=_(u"Available only"),
        required=False,
        default=False
    )


@form.default_value(field=ISearchAndReserveForm['recurrence_start'])
def start_default(data):
    return date.today()


@form.default_value(field=ISearchAndReserveForm['recurrence_end'])
def end_default(data):
    return date.today()


class SearchForm(BaseForm, AutoExtensibleForm, YourReservationsViewlet):
    permission = 'zope2.View'

    grok.context(IResourceBase)
    grok.require(permission)
    grok.name('search')

    ignoreContext = True

    template = grok.PageTemplateFile('templates/search.pt')
    schema = ISearchAndReserveForm

    enable_form_tabbing = False

    results = None
    searched = False

    # show the seantis.dir.facility viewlet if it's present
    show_facility_viewlet = True

    def update(self):
        super(SearchForm, self).update()
        self.widgets['timeframes'].value = self.context.json_timeframes()

    @property
    def available_actions(self):
        yield dict(name='search', title=_(u'Search'), css_class='context')

    @cached_property
    def options(self):
        params = self.parameters

        if not params:
            return None

        options = {}

        options['days'] = tuple(d.weekday for d in params['days'])
        options['minspots'] = params['minspots'] or 0
        options['available_only'] = params['available_only']
        options['whole_day'] = params['whole_day'] and 'yes' or 'any'

        if options['whole_day'] == 'yes':
            start = datetime.combine(params['recurrence_start'], time(0, 0))
            end = datetime.combine(
                params['recurrence_end'], time(23, 59, 59, 999999)
            )
        else:
            start_time = params['start_time'] or time(0, 0)
            end_time = params['end_time'] or time(23, 59, 59, 999999)

            start = datetime.combine(params['recurrence_start'], start_time)
            end = datetime.combine(params['recurrence_end'], end_time)

        options['start'] = start
        options['end'] = end

        return options

    def handle_search(self):
        self.searched = True
        self.results = tuple(self.search())

    def search(self):
        if not self.options:
            return

        days = {
            0: _(u'Monday'),
            1: _(u'Tuesday'),
            2: _(u'Wednesday'),
            3: _(u'Thursday'),
            4: _(u'Friday'),
            5: _(u'Saturday'),
            6: _(u'Sunday')
        }

        scheduler = self.context.scheduler()
        whole_day_text = self.translate(_(u'Whole day'))

        def get_time_text(allocation):
            if allocation.whole_day:
                return whole_day_text
            else:
                return ' - '.join((
                    api.portal.get_localized_time(
                        allocation.display_start, time_only=True
                    ),
                    api.portal.get_localized_time(
                        allocation.display_end, time_only=True
                    ),
                ))

        for allocation in scheduler.search_allocations(**self.options):

            availability, text, allocation_class = utils.event_availability(
                self.context, self.request, scheduler, allocation
            )

            day = ', '.join((
                days[allocation.display_start.weekday()],
                api.portal.get_localized_time(
                    allocation.display_start, long_format=False
                )
            ))

            yield {
                'id': allocation.id,
                'day': day,
                'time': get_time_text(allocation),
                'class': utils.event_class(availability),
                'text': ', '.join(text.split('\n'))
            }
