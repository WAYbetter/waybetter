from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from sharded_counters.models import SimpleCounterShard, GeneralCounterShard

def show(request):
    template_context = {
      'simpletotal': SimpleCounterShard.get_count(),
      'generaltotal': GeneralCounterShard.get_count('FOO')
    }
    return render_to_response('sharded_counters/counter.html', template_context,
        context_instance=RequestContext(request))

def increment(request):
    if request.method == 'POST':
        counter = request.POST['counter']
    if counter == 'simple':
      SimpleCounterShard.increment()
    else:
      GeneralCounterShard.increment('FOO')
    return HttpResponseRedirect('/show/')
