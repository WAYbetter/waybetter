from django.core.cache import cache
from django.db import models, DEFAULT_DB_ALIAS
from django.db.transaction import commit_on_success
try:
    from functools import wraps
except ImportError:
    from django.utils.functional import wraps  # Python 2.3, 2.4 fallback.
import random

def commit_locked(func_or_using=None):
    """
    Decorator that locks rows on DB reads.
    """
    # TODO GAE: Move this into backends.
    # TODO GAE: Add support for post_save_committed and post_delete_committed
    # signals which are sent after successful commit.
    # TODO GAE: Check if we're already in a transaction and if so, call
    # function directly?
    def inner_commit_locked(func, using=None):
        def _commit_locked(*args, **kw):
            from google.appengine.api.datastore import RunInTransaction
            return RunInTransaction(func, *args, **kw)
        return commit_on_success(wraps(func)(_commit_locked))
    if func_or_using is None:
        func_or_using = DEFAULT_DB_ALIAS
    if callable(func_or_using):
        return inner_commit_locked(func_or_using, DEFAULT_DB_ALIAS)
    return lambda func: inner_commit_locked(func, func_or_using)

class SimpleCounterShard(models.Model):
    """Shards for the counter"""
    count = models.IntegerField(default=0)
    name = models.CharField(primary_key=True, max_length=500)

    NUM_SHARDS = 20
    @classmethod
    def get_count(cls):
        """Retrieve the value for a given sharded counter."""
        total = 0
        for counter in SimpleCounterShard.objects.all():
            total += counter.count
        return total

    @classmethod
    @commit_locked
    def increment(cls):
        """Increment the value for a given sharded counter."""
        index = random.randint(0, SimpleCounterShard.NUM_SHARDS - 1)
        shard_name = 'shard' + str(index)
        counter = SimpleCounterShard.objects.get_or_create(pk=shard_name)[0]
        counter.count += 1
        counter.save()
  
class GeneralCounterShardConfig(models.Model):
    """Tracks the number of shards for each named counter."""
    name = models.CharField(primary_key=True, max_length=500)
    num_shards = models.IntegerField(default=20)

    @classmethod
    @commit_locked
    def increase_shards(cls, name, num):
        """Increase the number of shards for a given sharded counter.
        Will never decrease the number of shards.

        Parameters:
        name - The name of the counter
        num - How many shards to use

        """
        config = GeneralCounterShardConfig.objects.get_or_create(pk=name)[0]
        if config.num_shards < num:
            config.num_shards = num
            config.save()

class GeneralCounterShard(models.Model):
    """Shards for each named counter"""
    shard_name = models.CharField(primary_key=True, max_length=500)
    name = models.CharField(max_length=500)
    count = models.IntegerField(default=0)

    @classmethod
    def get_count(cls, name):
        """Retrieve the value for a given sharded counter.

        Parameters:
        name - The name of the counter
        """
        total = cache.get(name)
        if total is None:
            total = 0
            for counter in GeneralCounterShard.objects.all().filter(name=name):
                total += counter.count
            cache.add(name, str(total), 60)
        return total

    @classmethod
    @commit_locked
    def increment_txn(cls, config, name):
        index = random.randint(0, config.num_shards - 1)
        shard_name = name + str(index)
        counter = GeneralCounterShard.objects.get_or_create(pk=shard_name,
            name=name)[0]
        counter.count += 1
        counter.save()

    @classmethod
    def increment(cls, name):
        """Increment the value for a given sharded counter.

        Parameters:
        name - The name of the counter
        """
        @commit_locked
        def get_or_create_config_txn(name):
            return GeneralCounterShardConfig.objects.get_or_create(pk=name)[0]
        
        config = get_or_create_config_txn(name)
        GeneralCounterShard.increment_txn(config, name)
        cache.incr(name)
