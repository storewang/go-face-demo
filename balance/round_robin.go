package balance

func init() {
	factories[R2Balancer] = NewRoundRobin
}

type RoundRobin struct {
	BaseBalancer
	i uint64
}

func NewRoundRobin(hosts []string) Balancer {
	return &RoundRobin{
		i: 0,
		BaseBalancer: BaseBalancer{
			hosts: hosts,
		},
	}
}
func (r *RoundRobin) Balance(_ string) (string, error) {
	r.RLock()
	defer r.RUnlock()
	if len(r.hosts) == 0 {
		return "", NoHostError
	}
	host := r.hosts[r.i%uint64(len(r.hosts))]
	r.i++
	return host, nil
}
