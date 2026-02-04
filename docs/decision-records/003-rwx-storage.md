# ADR-003: ReadWriteMany (RWX) Storage Requirement

**Status**: Accepted  
**Date**: 2026-01-20  
**Decision Makers**: Infrastructure Team, Development Team  
**Related**: Phase 4 Implementation

## Context

Bots EDI processes EDI files through multiple services that need concurrent access to shared directories:
- Webserver uploads files to input directories
- Engine reads from input, writes to output
- Job queue processes files in work directories
- All services write logs to shared location

We needed to determine the storage access mode for Kubernetes PVCs.

### Storage Access Modes

**ReadWriteOnce (RWO)**:
- Volume can be mounted read-write by a single node
- Multiple pods on same node can access
- Standard for most applications

**ReadWriteMany (RWX)**:
- Volume can be mounted read-write by multiple nodes
- Any pod on any node can access
- Requires network filesystem

**ReadOnlyMany (ROX)**:
- Volume can be mounted read-only by multiple nodes
- Not applicable for our use case

## Options Considered

### Option 1: ReadWriteOnce with Pod Affinity
- **Approach**: Force all pods to same node using affinity
- **Storage**: Local-path, HostPath, cloud block storage
- **Pros**:
  - Faster I/O (local storage)
  - More storage class options
  - Lower cost
- **Cons**:
  - Single point of failure (node failure = all pods down)
  - No true high availability
  - Scheduling constraints
  - Can't use multi-node cluster benefits

### Option 2: ReadWriteMany with Network Filesystem
- **Approach**: Use NFS, CephFS, or Longhorn with RWX
- **Storage**: Network-attached storage
- **Pros**:
  - Pods can run on any node
  - True high availability
  - Leverages Kubernetes scheduling
  - Node failure only affects pods on that node
- **Cons**:
  - Slightly slower I/O (network overhead)
  - Requires RWX-capable storage class
  - More complex storage setup

### Option 3: Object Storage (S3-compatible)
- **Approach**: Use S3/MinIO for file storage
- **Storage**: Object store with FUSE mount
- **Pros**:
  - Highly scalable
  - Built-in replication
  - Web-accessible
- **Cons**:
  - Performance overhead (FUSE layer)
  - File locking issues
  - Not POSIX-compliant
  - Application changes required

### Option 4: Database-Backed Storage
- **Approach**: Store files as BLOBs in database
- **Storage**: MySQL BLOB fields
- **Pros**:
  - No shared filesystem needed
  - Transactional consistency
- **Cons**:
  - Massive application refactoring
  - Poor performance for large files
  - Database bloat
  - Not viable for existing codebase

## Decision

**Chosen**: Option 2 - ReadWriteMany with Network Filesystem

We will use RWX PVCs backed by NFS (t1-shiva-nfs storage class):
- `bots-edi-data-pvc` (20Gi, RWX) - EDI files
- `bots-edi-logs-pvc` (5Gi, RWX) - Logs
- `bots-edi-config-pvc` (1Gi, RWX) - Runtime config

## Rationale

### Why RWX is Mandatory

**File Access Patterns**:
```
Webserver (Node A) → Write to /data/input/file1.edi
Engine (Node B)    → Read from /data/input/file1.edi
Engine (Node B)    → Write to /data/output/file1.xml
Webserver (Node A) → Read from /data/output/file1.xml
```

**Concurrent Access**:
- Webserver: 3 replicas (scheduled across nodes)
- Job Queue: 1 replica (could be on any node)
- Engine CronJob: Runs on available node

**Failure Scenarios**:
- With RWO + affinity: Node failure = complete outage
- With RWX: Node failure = reschedule pods to other nodes

### Why Not RWO
- Forces single node deployment (defeats Kubernetes multi-node)
- No HA without custom file synchronization
- Pod scheduling limitations
- Not acceptable for production

### Why Not Object Storage
- Bots EDI uses POSIX file operations extensively
- File locking used for concurrency control
- No budget for application refactoring
- Performance concerns for frequent small file operations

## Implementation

### Storage Class
```yaml
# Using existing NFS storage class
storageClassName: t1-shiva-nfs
```

### PVC Definitions
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: bots-edi-data-pvc
spec:
  accessModes:
    - ReadWriteMany  # Critical: RWX required
  resources:
    requests:
      storage: 20Gi
  storageClassName: t1-shiva-nfs
```

### Volume Mounts
```yaml
volumeMounts:
  - name: data
    mountPath: /home/bots/.bots
    # All services mount at same path
```

## Consequences

### Positive
- ✅ Pods can run on any node (true HA)
- ✅ Kubernetes scheduler has full flexibility
- ✅ Node failure doesn't cause service outage
- ✅ Easy to scale replicas
- ✅ Standard Kubernetes deployment pattern
- ✅ Works with existing code (no changes needed)

### Negative
- ❌ Requires NFS or RWX-capable storage
- ❌ Network I/O overhead (~10-20% slower than local)
- ❌ Not all cloud providers support RWX easily
- ❌ NFS single point of failure (mitigated by HA NFS)
- ❌ File locking performance concerns

### Mitigations
- Use HA NFS server (DRBD, Pacemaker)
- Optimize NFS mount options (async, noatime)
- Monitor I/O performance metrics
- Consider local SSD on NFS server
- Cache frequently accessed files in memory

## Performance Considerations

### Benchmarks (Anticipated)
- Local storage: ~500 MB/s sequential read
- NFS over gigabit: ~100 MB/s sequential read
- Typical EDI file: 10-500 KB
- Expected impact: Minimal (network not bottleneck)

### Optimization
```yaml
# NFS mount options
mountOptions:
  - nfsvers=4.1
  - tcp
  - timeo=600
  - retrans=2
  - hard
```

## Storage Class Alternatives

### Tested
- ✅ **NFS (t1-shiva-nfs)**: Working, recommended
- ✅ **Longhorn**: Works with RWX, slower than NFS
- ❌ **Local-path**: No RWX support
- ❌ **HostPath**: No RWX support

### Cloud Providers
- **AWS**: EFS (supports RWX)
- **Azure**: Azure Files (supports RWX)
- **GCP**: Filestore (supports RWX)
- **On-prem**: NFS, CephFS, GlusterFS

## File Locking Strategy

Bots EDI uses file-based locking:
```python
# bots/botssys/mutex.py
lockfile = open(lockfilepath, 'w')
fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX)
```

**NFS Considerations**:
- NFS v4+ has improved locking
- `hard` mount option ensures reliability
- Tested with concurrent pod access
- No issues observed in testing

## Alternatives Rejected

### Custom File Sync
```yaml
# Rejected: Syncthing/rsync between pods
- initContainer: syncthing
```
**Why**: Complex, eventual consistency issues, defeats purpose

### Distributed Filesystem
```yaml
# Rejected: GlusterFS/CephFS on cluster nodes
- daemonSet: glusterd
```
**Why**: Operational overhead, complexity, NFS sufficient

### Sidecar Pattern
```yaml
# Rejected: Each pod with local storage + sync sidecar
- sidecar: file-sync
```
**Why**: Inconsistency, complexity, not needed

## References

- [Kubernetes Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [NFS Best Practices](https://kubernetes.io/docs/concepts/storage/volumes/#nfs)
- [Storage Class Provisioners](https://kubernetes.io/docs/concepts/storage/storage-classes/)

## Review

This decision should be reviewed if:
- I/O performance becomes a bottleneck
- File locking issues emerge
- Storage costs become prohibitive
- New storage technologies emerge (e.g., improved object storage)
- Application can be refactored to eliminate shared filesystem

## Monitoring

Track these metrics:
- NFS mount latency
- I/O wait time
- File operation errors
- Lock contention
- Storage capacity usage
