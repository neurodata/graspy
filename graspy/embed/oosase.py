# oosase.py
# Created by Hayden Helm on 2019-04-22.
# Email: hhelm2@jhu.edu
import warnings

from .base import BaseEmbed
from .svd import selectSVD
from ..utils import import_graph, get_lcc, is_fully_connected, is_symmetric

import numpy as np
from sklearn.utils.validation import check_is_fitted
from sklearn.utils import check_array
import networkx as nx


class OutOfSampleAdjacencySpectralEmbed(BaseEmbed):
    r"""
    Class for computing the out of sample adjacency spectral embedding of a graph.
    
    The adjacency spectral embedding (ASE) is a k-dimensional Euclidean representation of 
    the graph based on its adjacency matrix [1]_. It relies on an SVD to reduce the dimensionality
    to the specified k, or if k is unspecified, can find a number of dimensions automatically
    (see graspy.embed.selectSVD). The out of sample adjacency spectral embedding (OOSASE) considers
    the ASE of an induced subgraph of the original graph. To embed "out of sample" vertices, a projection
    matrix learned from the in sample embedding is used [2]_.

    Parameters
    ----------
    n_components : int or None, default = None
        Desired dimensionality of output data. If "full", 
        n_components must be <= min(X.shape). Otherwise, n_components must be
        < min(X.shape). If None, then optimal dimensions will be chosen by
        ``select_dimension`` using ``n_elbows`` argument.
    n_elbows : int, optional, default: 2
        If `n_components=None`, then compute the optimal embedding dimension using
        `select_dimension`. Otherwise, ignored.
    algorithm : {'randomized' (default), 'full', 'truncated'}, optional
        SVD solver to use:

        - 'randomized'
            Computes randomized svd using 
            ``sklearn.utils.extmath.randomized_svd``
        - 'full'
            Computes full svd using ``scipy.linalg.svd``
        - 'truncated'
            Computes truncated svd using ``scipy.sparse.linalg.svd``
    n_iter : int, optional (default = 5)
        Number of iterations for randomized SVD solver. Not used by 'full' or 
        'truncated'. The default is larger than the default in randomized_svd 
        to handle sparse matrices that may have large slowly decaying spectrum.
    check_lcc : bool , optional (default = True)
        Whether to check if input graph is connected. May result in non-optimal 
        results if the graph is unconnected. If True and input is unconnected,
        a UserWarning is thrown. Not checking for connectedness may result in 
        faster computation.
    in_sample_proportion : float , optional (default = 1)
        If in_sample_idx is None, the proportion of in sample vertices to use for
        initial embedding.
    in_sample_idx : array-like , optional (default = None)
    connected_attempts : integer , optional (default = 1000)
        Number of sets of indices 
    semi_supervised : boolean , optional (default = False)
    random_state : integer , optional (default = None)
        Random seed used to generate in sample indices. If None, random_state
        is a random integer between 0 and 10**6

    Attributes
    ----------
    latent_left_ : array, shape (n_in_samples, n_components)
        Estimated left latent positions of the graph.
    singular_values_ : array, shape (n_components)
        Singular values associated with the latent position matrices

    See Also
    --------
    graspy.embed.selectSVD
    graspy.embed.select_dimension

    Notes
    -----
    The singular value decomposition: 

    .. math:: A = U \Sigma V^T

    is used to find an orthonormal basis for a matrix, which in our case is the adjacency
    matrix of the graph. These basis vectors (in the matrices U or V) are ordered according 
    to the amount of variance they explain in the original matrix. By selecting a subset of these
    basis vectors (through our choice of dimensionality reduction) we can find a lower dimensional 
    space in which to represent the graph.

    References
    ----------
    .. [1] Sussman, D.L., Tang, M., Fishkind, D.E., Priebe, C.E.  "A
       Consistent Adjacency Spectral Embedding for Stochastic Blockmodel Graphs,"
       Journal of the American Statistical Association, Vol. 107(499), 2012
    .. [2] Levin, K., Roosta-Khorasani, F., Mahoney, M. W., & Priebe, C. E. (2018). Out-of-sample 
        extension of graph adjacency spectral embedding. PMLR: Proceedings of Machine Learning 
        Research, 80, 2975-2984.
    """

    def __init__(
        self,
        n_components=None,
        n_elbows=2,
        algorithm="randomized",
        n_iter=5,
        check_lcc=True,
        in_sample_proportion=1,
        in_sample_idx=None,
        connected_attempts=100,
        semi_supervised=False,
        random_state=None,
    ):
        super().__init__(
            n_components=n_components,
            n_elbows=n_elbows,
            algorithm=algorithm,
            n_iter=n_iter,
            check_lcc=check_lcc,
        )

        if random_state is None:
            random_state = np.random.randint(10 ** 6)
        np.random.seed(random_state)

        if in_sample_proportion <= 0 or in_sample_proportion > 1:
            if in_sample_idx is None:
                msg = (
                    "must give either proportion of in sample indices or a list"
                    + "of in sample vertices"
                )
                raise ValueError(msg)
        self.connected_attempts = connected_attempts
        self.semi_supervised = semi_supervised
        self.in_sample_proportion = in_sample_proportion
        self.in_sample_idx = in_sample_idx

    def fit(self, graph, y=None):
        """
        Fit ASE model to input graph

        Parameters
        ----------
        graph : array_like or networkx.Graph
            Input graph to embed.

        Returns
        -------
        self : returns an instance of self.
        """

        if is instance(graph, np.ndarray):
            check_array(graph)
            graph = nx.Graph(graph).copy()

        if is instance(graph, nx.Graph):
            if not is_symmetric(graph):
                msg = (
                    'symmetric graphs only'
                    )
                raise ValueError(msg)
            connected_comps = nx.connected_components(graph)
            indices = [list(c) for c in connected_comps]
            lens = np.array([len(c) for c in connected_comps])
            if np.count_nonzero(lens - 1) != len(lens):
                msg = (
                    'singletons in graph'
                    )
                raise ValueError(msg)
        elif:
            msg = (
                'only arrays and networkx graphs allowed'
                )
            raise TypeError(msg)

        A = import_graph(graph)
        N = A.shape[0]

        if self.in_sample_proportion is None:
            self.in_sample_proportion = len(self.in_sample_idx) / N

        counts = [int(np.round(self.in_sample_proportion*i)) for i in lens]

        if self.in_sample_idx is None:
            if self.in_sample_proportion == 1:
                self.in_sample_idx = range(N)
            else:
                self.in_sample_idx = self._stratified_sample(connected_comps, counts)
        else:
            self.in_sample_proportion = len(self.in_sample_idx) / N

        in_sample_A = A[np.ix_(self.in_sample_idx, self.in_sample_idx)]

        if self.check_lcc:
            if self.in_sample_proportion < 1:
                c = 0
                while (
                    not is_fully_connected(in_sample_A) and c < self.connected_attempts
                ):
                    self.in_sample_idx = np.random.choice(N, n)
                    in_sample_A = A[np.ix_(self.in_sample_idx, self.in_sample_idx)]
                    c += 1
                if c == self.connected_attempts:
                    msg = (
                        "Induced subgraph is not fully connected. Attempted to find connected"
                        + "induced subgraph {} times. Results may not be optimal."
                        + "Try increasing proportion of in sample vertices.".format(
                            connected_attempts
                        )
                    )
                    warning.warn(msg, UserWarning)
            else:
                if not is_fully_connected(A):
                    msg = (
                        "Input graph is not fully connected. Results may not"
                        + "be optimal. You can compute the largest connected component by"
                        + "using ``graspy.utils.get_lcc``."
                    )
                    warnings.warn(msg, UserWarning)

        self._reduce_dim(in_sample_A)
        return self

    def _stratified_sample(self, lists, counts):
        """
        Stratified sampling.

        Parameters
        ----------
        lists : list
            A list of list of objects to sample from.

        counts : array_like
            An array or list of sample counts from each list in lists.

        Returns
        -------
        sample : array
            Stratified sample.
        """
        ints = np.sum(np.array([is not instance(c, int) for c in counts]))
        if ints > 0:
            msg = (
                'integer counts only'
                )
            raise ValueError(msg)

        len_lists = np.array([len(list_) for list_ in lists])
        if np.sum(len_lists > counts) > 0:
            msg = (
                'trying to sample n > len(list) things'
                )
            raise ValueError(msg)

        sample = np.concatenate([np.random.choice(lists[i], counts[i]) for i in range(len(lists))])
        return sample

    def predict(self, X):
        """
        Embed out of sample vertices.

        Parameters
        ----------
        X : array_like, shape (m, n)
            m stacked similarity lists, where the jth entry of the ith row corresponds to
            the similarity of the ith out of sample observation to the jth in sample
            observation.

        Returns
        -------
        oos_embedding : array, shape (m, d)
            The embedding of the out of sample vertices.
        """

        # Check if fit is already called
        check_is_fitted(self, ["latent_left_"], all_or_any=all)

        is_embedding = self.latent_left_
        n = is_embedding.shape[0]

        # Type checking
        check_array(
            X,
            ensure_2d=False,
            allow_nd=False,
            ensure_min_samples=1,
            ensure_min_features=n,
        )

        if X.ndim is 1:
            X = X.reshape((1, -1))
            X = X.T
            m = 1
        elif X.shape[1] > n:
            msg = "Similarity vector must be of length n"
            raise ValueError(msg)
        else:
            m = X.shape[0]

        row_sums = np.sum(X, axis=1)
        if np.count_nonzero(row_sums) != m:
            msg = (
                "At least one adjacency vector is the zero vector."
                + " It is recommended to first embed nodes with non-zero adjacency vectors"
                + " with self.semi_supervised = True and embed the nodes"
                + " with zero adjacencies"
            )
            raise ValueError(msg)

        oos_embedding = X @ np.linalg.pinv(is_embedding).T

        if self.semi_supervised:
            self.latent_left_ = np.concatenate(
                (self.latent_left_, oos_embedding), axis=0
            )

        return oos_embedding

    def fit_predict(self, graph):
        """
        Perform both in sample and out of sample adjacency spectral embedding.

        Parameters
        ----------
        graph : array-like or networkx.Graph
            Input graph to embed.

        Returns
        -------
        embedding : array
            Embedding of all vertices in graph.
        """

        A = import_graph(graph)
        self.fit(A)

        N = A.shape[0]
        n = len(self.in_sample_idx)
        out_sample_idx = [i for i in range(N) if i not in self.in_sample_idx]
        oos = self.predict(A[np.ix_(out_sample_idx, self.in_sample_idx)])

        embedding = np.zeros((N, self.latent_left_.shape[1]))
        embedding[self.in_sample_idx] = self.latent_left_[:n]
        embedding[out_sample_idx] = oos

        if self.semi_supervised:
            self.latent_left = embedding

        return embedding