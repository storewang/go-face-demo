package balance

import "sync"

type BaseBalancer struct {
	sync.RWMutex
	hosts []string
}

func (b *BaseBalancer) Add(host string) {
	b.Lock()
	defer b.Unlock()
	for _, h := range b.hosts {
		if h == host {
			return
		}
	}
	b.hosts = append(b.hosts, host)
}
func (b *BaseBalancer) Remove(host string) {
	b.Lock()
	defer b.Unlock()
	for i, h := range b.hosts {
		if h == host {
			b.hosts = append(b.hosts[:i], b.hosts[i+1:]...)
			return
		}
	}
}
func (b *BaseBalancer) Balance(key string) (string, error) {
	return "", nil
}
func (b *BaseBalancer) Inc(_ string)  {}
func (b *BaseBalancer) Done(_ string) {}
