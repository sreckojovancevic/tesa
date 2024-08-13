from rq import Worker, Queue, Connection
import redis

redis_url = 'redis://localhost:6379'
conn = redis.from_url(redis_url)

if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(map(Queue, ['default']))
        worker.work()
