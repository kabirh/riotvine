"""

Twitter AMQP exchange

Message routing key format:
    twitter.<api_type>.<method>
        api_type: 
            - get (throttled @ 2 Twitter requests per second) (persistent)
                  method:
                      - get_followers (correlation_id=twitter_id, reply_to=twitter/twitter.get.get_followees)
                      - get_followees (correlation_id=twitter_id, reply_to=twitter/twitter.compute.get_friends)
            - compute (persistent)
                  method:
                       - get_friends (correlation_id=twitter_id, reply_to=twitter/twitter.compute.save_friends)
                       - save_friends (delete correlation data when done)
            - search (to be implemented later) (non-persistent)
                  method:
                      - search

Topic Exchange: twitter (durable)

Queue:
    - twitter_get (durable)
        routing_key = twitter.get.#
    - twitter_compute (durable)
        routing_key = twitter.compute.#
    - twitter_search
        routing_key = twitter.search.search

"""


