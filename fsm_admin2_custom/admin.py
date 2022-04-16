from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django_currentuser.middleware import get_current_user
from django_fsm import TransitionNotAllowed
from fsm_admin2.admin import FSMTransitionMixin, _get_transition_title
from django.utils.translation import gettext as _

def _get_transition_form(transition, obj=None):
    form = transition.custom.get('form')
    if not form:
        form_func = transition.custom.get('form_func')
        if form_func:
            form = form_func(obj)
    return form


class FSMTransitionCustomMixin(FSMTransitionMixin):
    fsm_transition_buttons_template = 'fsm_admin2_custom/fsm_transition_buttons.html'

    def __init_subclass__(cls, **kwargs):
        for fsm_field in cls.fsm_fields:
            setattr(cls, _get_display_func_name(fsm_field), _get_display_func(fsm_field))

    def fsm_transition_view_extra_context(self, obj):
        return {}

    def get_form_kwargs(self, form_class, obj):
        return {}

    def fsm_transition_view(self, request, *args, **kwargs):
        transition_name = request.GET.get('transition')
        obj = self.get_object(request, kwargs['object_id'])
        transition_method = getattr(obj, transition_name)
        if not hasattr(transition_method, '_django_fsm'):
            return HttpResponseBadRequest(f'{transition_name} is not a transition method')

        transitions = transition_method._django_fsm.transitions
        if isinstance(transitions, dict):
            transitions = list(transitions.values())
        transition = transitions[0]

        form_class = _get_transition_form(transition, obj=obj)
        if form_class:
            context = self.fsm_transition_view_extra_context(obj)
            if request.method == 'POST':
                form = form_class(request.POST, self.get_form_kwargs(form_class, obj))
                if form.is_valid():
                    transition_method(by=get_current_user(), **form.cleaned_data)
                    obj.save()
                else:
                    context.update({'transition': transition_name, 'form': form})
                    return render(
                        request,
                        self.fsm_transition_form_template,
                        context
                    )
            else:
                form = form_class(self.get_form_kwargs(form_class, obj))
                context.update({'transition': transition_name, 'form': form})
                return render(
                    request,
                    self.fsm_transition_form_template,
                    context
                )
        else:
            try:
                transition_method(by=get_current_user())
            except TransitionNotAllowed:
                self.message_user(
                    request,
                    'Transition %(transition)s is not allowed'
                    % {'transition': _get_transition_title(transition)},
                    messages.ERROR,
                )
            else:
                obj.save()
                self.message_user(
                    request,
                    'Transition %(transition)s applied'
                    % {'transition': _get_transition_title(transition)},
                    messages.SUCCESS,
                )
        info = self.model._meta.app_label, self.model._meta.model_name
        return redirect('admin:%s_%s_change' % info, object_id=obj.id)


def _get_display_func_name(fsm_field_name):
    return f'fsm_display_{fsm_field_name}'



def _get_display_func(field_name):
    def display_func(self, obj=None):
        if obj is None:
            return ''
        transitions = getattr(obj, f'get_available_user_{field_name}_transitions')(self.request.user)

        info = obj._meta.model._meta.app_label, obj._meta.model._meta.model_name
        url = reverse('admin:%s_%s_transition' % info, kwargs={'object_id': obj.id})

        buttons = [{
            'url': f'{url}?transition={transition.name}',
            'title': _get_transition_title(transition)
        } for transition in transitions if transition.custom.get('admin', False)]

        return render_to_string(self.fsm_transition_buttons_template, {'transition_buttons': buttons})

    display_func.short_description = _('{} Transitions'.format(field_name.title().replace('_', ' ')))
    return display_func


def _get_transition_title(transition):
    if transition.custom.get('short_description'):
        return transition.custom.get('short_description')

    if hasattr(transition.target, 'label'):
        return transition.target.label

    return transition.name

