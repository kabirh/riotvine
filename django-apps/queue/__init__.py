from django.conf import settings
from django.db import transaction


class ActionItemProcessorBase(object):
    """Each ActionItem processor extends this class.

    A Processor class defines methods named after the action they handle for
    a given ActionItem instance (i.e. `ActionItem.action`.) The method name is
    simply the lowercased ActionItem.action name with dashes replaced by 
    underscores. The method must return `True` for a successful completion of the 
    task and `False` otherwise.

    For example, CampaignProcessor.generate_tickets is responsible for handling
    the ActionItem whose category is 'campaign' and action is 'generate-tickets'.

    """
    @transaction.commit_on_success
    def perform_action(self, action_item):
        """Dynamically call method `<action_item.action>` on subclass.

        If called method is not found, return `False`.
        Otherwise, return the result of calling the method (which must be a
        `boolean` too.)
        
        If the called method returns `False`, the action_item will be marked
        as 'wont-perform' (it won't be retried.)
        
        If the called method raises an Exception, the action_item will be
        retried in the next run.

        """
        method_name = action_item.action.replace('-', '_').lower()
        method_instance = getattr(self, method_name, None)
        if callable(method_instance):
            result = method_instance(action_item.target)
        else:
            result = False
        return result


class ActionItemProcessorRegistry(object):
    def __init__(self):
        self._registry = {}

        # settings.QUEUE_REGISTERED_PROCESSORS is a mapping of ActionItem.category to
        # the ActionItem processor class that's responsible for handling all actions for
        # that category. The class value is a fully qualified class name and not a class
        # instance. For example: campaign.queue.CampaignProcessor
        _REGISTERED_PROCESSORS = getattr(settings, 'QUEUE_REGISTERED_PROCESSORS', {})

        for category, processor_class in _REGISTERED_PROCESSORS.iteritems():
             # Dynamically import class from the module.
            mod, cls = processor_class.rsplit('.', 1)
            mod = __import__(mod, globals(), locals(), [''])
            cls = getattr(mod, cls)
            processor = cls()
            if isinstance(processor, ActionItemProcessorBase):
                self._registry[category.lower()] = processor # register an instance of processor class for this category.
            else:
                raise Exception("%s is not a valid ActionItem processor -- it is not derived from queue.ActionItemProcessorBase." % processor_class)

    def get_processor(self, category):
        """Return the processor instance for a category or None if category has 
        no registered processor.

        `category` is case-insensitive.

        """
        return self._registry.get(category.lower(), None)


registry = ActionItemProcessorRegistry()

