from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import render, redirect
from django_currentuser.middleware import get_current_user
from django_fsm import TransitionNotAllowed
from fsm_admin2.admin import FSMTransitionMixin, _get_transition_title


def _get_transition_form(transition, obj=None):
    form = transition.custom.get('form')
    if not form:
        form_func = transition.custom.get('form_func')
        if form_func:
            form = form_func(obj)
    return form


class FSMTransitionCustomMixin(FSMTransitionMixin):

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
