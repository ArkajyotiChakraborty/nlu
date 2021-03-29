import nlu
from nlu.pipeline import NLUPipeline

import logging
from nlu.pipe_components import SparkNLUComponent
logger = logging.getLogger('nlu')

import inspect
from dataclasses import dataclass

@dataclass
# class ComponentResolutionInformation:
#     """Class holding information about a feature that needs to be resolved  """
#     name: str
#     unit_price: float
#     quantity_on_hand: int = 0
#
#     def total_cost(self) -> float:
#         return self.unit_price * self.quantity_on_hand

class PipelineQueryVerifier():
    '''
        Pass a list of NLU components to the pipeline (or a NLU pipeline)
        For every component, it checks if all requirements are met.
        It checks and fixes the following issues  for a list of components:
        1. Missing Features / component requirements
        2. Bad order of components (which will cause missing features.
        3. Check Feature naems in the output
        4. Check wether pipeline needs to be fitted
    '''

    @staticmethod
    def is_untrained_model(component):
        '''
        Check for a given component if it is an embelishment of an traianble model.
        In this case we will ignore embeddings requirements further down the logic pipeline
        :param component: Component to check
        :return: True if it is trainable, False if not
        '''
        if 'is_untrained' in dict(inspect.getmembers(component.info)).keys(): return True
        return False

    @staticmethod
    def has_embeddings_requirement(component):
        '''
        Check for the input component, wether it depends on some embedding. Returns True if yes, otherwise False.
        :param component:  The component to check
        :return: True if the component needs some specifc embedding (i.e.glove, bert, elmo etc..). Otherwise returns False
        '''

        if type(component) == list or type(component) == set:
            for feature in component:
                if 'embed' in feature: return True
            return False
        else:
            if component.info.type == 'word_embeddings': return False
            if component.info.type == 'sentence_embeddings': return False
            if component.info.type == 'chunk_embeddings': return False
            for feature in component.info.inputs:
                if 'embed' in feature: return True
        return False

    @staticmethod
    def extract_storage_ref_AT_column(component, col='input'):
        '''
        Extract <col>_embed_col@storage_ref notation from a component if it has a storage ref, otherwise '

        :param component:  To extract notation from
        :cols component:  Wether to extract for the input or output col
        :return: '' if no storage_ref, <col>_embed_col@storage_ref otherwise
        '''
        if not PipelineQueryVerifier.nlu_component_has_storage_ref(component) : return ''
        if   col =='input'  : e_col    = next(filter(lambda s : 'embed' in s, component.info.inputs))
        elif col =='output' : e_col    = next(filter(lambda s : 'embed' in s, component.info.outputs))

        stor_ref = PipelineQueryVerifier.extract_storage_ref_from_component(component)
        return e_col + '@' + stor_ref


    @staticmethod
    def has_embeddings_provisions(component):
        '''
        Check for the input component, wether it depends on some embedding. Returns True if yes, otherwise False.
        :param component:  The component to check
        :return: True if the component needs some specifc embedding (i.e.glove, bert, elmo etc..). Otherwise returns False
        '''
        if type(component) == type(list) or type(component) == type(set):
            for feature in component:
                if 'embed' in feature: return True
            return False
        else:
            for feature in component.info.outputs:
                if 'embed' in feature: return True
        return False

    @staticmethod
    def clean_irrelevant_features(component_list):
        '''
        Remove irrelevant features from a list of component features
        :param component_list: list of features
        :return: list with only relevant feature names
        '''
        # remove irrelevant missing features for pretrained models
        if 'text' in component_list: component_list.remove('text')
        if 'raw_text' in component_list: component_list.remove('raw_text')
        if 'raw_texts' in component_list: component_list.remove('raw_texts')
        if 'label' in component_list: component_list.remove('label')
        if 'sentiment_label' in component_list: component_list.remove('sentiment_label')
        return component_list


    @staticmethod
    def extract_storage_ref(component):
        """Extract storage ref from either a NLU component or NLP Annotator. First cheks if annotator has storage ref, otherwise check NLU attribute"""
        if PipelineQueryVerifier.has_storage_ref(component):
            if hasattr(component.info,'storage_ref') : return component.info.storage_ref
            if PipelineQueryVerifier.nlp_component_has_storage_ref(component.model) : return PipelineQueryVerifier.nlu_extract_storage_ref_nlp_model(component)
        return ''

    @staticmethod
    def nlu_extract_storage_ref_nlp_model(component):
        """Extract storage ref from a NLU component which embelished a Spark NLP Annotator"""
        return component.model.extractParamMap()[component.model.getParam('storageRef')]

    @staticmethod
    def extract_storage_ref_from_component(component):
        """Extract storage ref from a NLU component which embelished a Spark NLP Annotator"""
        if PipelineQueryVerifier.nlu_component_has_storage_ref(component):
            return component.info.storage_ref
        else:
            return ''

    @staticmethod
    def has_component_storage_ref_or_anno_storage_ref(component):
        """Storage ref is either on the model or nlu component defined """
        if PipelineQueryVerifier.nlp_component_has_storage_ref(component.model): return True
        if PipelineQueryVerifier.nlu_component_has_storage_ref(component) : return True

    @staticmethod
    def has_storage_ref(component):
        """Storage ref is either on the model or nlu component defined """
        return PipelineQueryVerifier.has_component_storage_ref_or_anno_storage_ref(component)



    @staticmethod
    def nlu_component_has_storage_ref(component):
        """Check if a storage ref is defined on the Spark NLP Annotator embelished by the NLU Component"""
        if hasattr(component.info, 'storage_ref'): return True
        return False

    @staticmethod
    def nlp_component_has_storage_ref(model):
        """Check if a storage ref is defined on the Spark NLP Annotator model"""
        for k, _ in model.extractParamMap().items():
            if k.name == 'storageRef': return True
        return False

    @staticmethod
    def extract_nlp_storage_ref_from_nlp_model_if_set(model):
        """Extract storage ref from a Spark NLP Annotator model"""
        if PipelineQueryVerifier.nlu_extract_storage_ref_nlp_model(model): return ''
        else : return PipelineQueryVerifier.extract_nlp_storage_ref_from_nlp_model(model)

    @staticmethod
    def nlp_extract_storage_ref_nlp_model(model):
        """Extract storage ref from a NLU component which embelished a Spark NLP Annotator"""
        return model.extractParamMap()[model.model.getParam('storageRef')]


    @staticmethod
    def check_if_storage_ref_is_satisfied(component_to_check:SparkNLUComponent, pipe:NLUPipeline, storage_ref_to_find:str):
        """Check if any other component in the pipeline has same storage ref as the input component..
        Returns 1. If
        If there is a candiate but it has different level, it will be returned as candidate

        If first condition is not satified, consults the namespace.storage_ref_2_nlp_ref

        """
        # If there is just 1 component, there is nothing to check
        if len(pipe.components) == 1: return False, None
        conversion_candidate = None
        conversion_type = ""
        logger.info(f'checking for storage={storage_ref_to_find} is avaiable in pipe..')
        # TODO RETURN CONVERSION TYPEEEE sent/chunk conversion!
        for c in pipe.components:
            if component_to_check.info.name != c.info.name:
                if PipelineQueryVerifier.has_storage_ref(c):
                    if PipelineQueryVerifier.extract_storage_ref(c) == storage_ref_to_find:
                        # Both components have Different Names AND their Storage Ref Matches up AND they both take in tokens -> Match
                        if 'token' in component_to_check.info.inputs and c.info.type == 'word_embeddings':
                            logger.info(f'Word Embedding Match found = {c.info.name}')
                            return True, None

                        # Since document and be substituted for sentence and vice versa if either of them matches up we have a match
                        if 'sentence_embeddings' in component_to_check.info.inputs and c.info.type == 'sentence_embeddings':
                            logger.info(f'Sentence Emebdding Match found = {c.info.name}')
                            return True, None

                        # component_to_check requires Sentence_embedding but the Matching Storage_ref component takes in Token
                        #   -> Convert the Output of the Match to SentenceLevel and feed the component_to_check to the new component
                        if 'sentence_embeddings' in component_to_check.info.inputs and c.info.type == 'word_embeddings':
                            logger.info(f'Sentence Embedding Conversion Candidate found={c.info.name}')
                            conversion_type      = 'word2sentence'
                            conversion_candidate = c

                        #analogus case as above for chunk
                        if 'chunk_embeddings' in component_to_check.info.inputs and c.info.type == 'word_embeddings': ## todo was "chunk_embeddings"
                            logger.info(f'Sentence Embedding Conversion Candidate found={c.info.name}')
                            conversion_type      = 'word2chunk'
                            conversion_candidate = c


        logger.info(f'No matching storage ref found')
        return False, conversion_candidate

    @staticmethod
    def is_embedding_provider(component:SparkNLUComponent) -> bool:
        """Check if a NLU Component returns embeddings """
        if 'embed' in component.info.outputs[0]:
            return True
        else:
            return False

    @staticmethod
    def is_embedding_consumer(component:SparkNLUComponent) -> bool:
        """Check if a NLU Component consumes embeddings """
        return any('embed' in i for i in component.info.inputs)


    @staticmethod
    def is_embedding_consumer(component:SparkNLUComponent) -> bool:
        """Check if a NLU Component consumes embeddings """
        return any('embed' in i for i in component.info.inputs)


    @staticmethod
    def extract_required_features_refless_from_pipe(pipe: NLUPipeline):
        """Extract provided features from pipe, which have no storage ref"""
        provided_features_no_ref = []
        for c in pipe:
            for feat in c.info.inputs:
                if 'embed' not in feat : provided_features_no_ref.append(feat)
        return  provided_features_no_ref

    @staticmethod
    def extract_required_features_ref_from_pipe(pipe: NLUPipeline):
        """Extract provided features from pipe, which have  storage ref"""
        provided_features_ref = []
        for c in pipe:
            for feat in c.info.inputs:
                if 'embed' in feat : provided_features_ref.append(feat +"@"+ PipelineQueryVerifier.extract_storage_ref(c))
        return provided_features_ref


    @staticmethod
    def extract_provided_features_refless_from_pipe(pipe: NLUPipeline):
        """Extract provided features from pipe, which have no storage ref"""
        provided_features_no_ref = []
        for c in pipe:
            for feat in c.info.outputs:
                if 'embed' not in feat : provided_features_no_ref.append(feat)
        return  provided_features_no_ref

    @staticmethod
    def extract_provided_features_ref_from_pipe(pipe: NLUPipeline):
        """Extract provided features from pipe, which have  storage ref"""
        provided_features_ref = []
        for c in pipe:
            for feat in c.info.outputs:
                if 'embed' in feat : provided_features_ref.append(feat +"@"+ PipelineQueryVerifier.extract_storage_ref(c))
        return provided_features_ref
    @staticmethod
    def check_if_pipe_trainable(pipe: NLUPipeline):
        """Check if  contains trainable moels """
        for c in pipe :
            if PipelineQueryVerifier.is_untrained_model(c): return True
        return False

    @staticmethod
    def extract_conversion_candidates(pipe, trainable):
        """ Extract either [] or a list of components that should be converted to chunk/sent embends"""
        components_for_sentence_embedding_conversion = []
        for component in pipe:
            if PipelineQueryVerifier.has_embeddings_requirement(component) and not trainable and PipelineQueryVerifier.has_storage_ref(component):
                # We check if Storage ref is satisfied by some component and if it also is matched output_level_wise (checked by check_if_storage_ref_is_satisfied).
                # If there storage_ref is satisfied, we add a converter right away and update cols
                storage_ref = PipelineQueryVerifier.extract_storage_ref(component)
                storage_ref_satisfied, conversion_candidate = PipelineQueryVerifier.check_if_storage_ref_is_satisfied(component, pipe, storage_ref)
                if not storage_ref_satisfied and conversion_candidate is not None: components_for_sentence_embedding_conversion.append(conversion_candidate)
        return components_for_sentence_embedding_conversion



    @staticmethod
    def get_missing_required_features_V2(pipe: NLUPipeline):
        provided_features_no_ref                = PipelineQueryVerifier.extract_provided_features_refless_from_pipe(pipe)
        required_features_no_ref                = PipelineQueryVerifier.extract_required_features_refless_from_pipe(pipe)
        provided_features_ref                   = PipelineQueryVerifier.extract_provided_features_ref_from_pipe(pipe)
        required_features_ref                   = PipelineQueryVerifier.extract_required_features_ref_from_pipe(pipe)
        is_trainable                            = PipelineQueryVerifier.check_if_pipe_trainable(pipe)

        sentence_emb_conversion_candidates      = []
        sentence_chunk_conversion_candidates    = []
        components_for_ner_conversion           = []
        pipe.has_trainable_components           = True
    @staticmethod
    def get_missing_required_features(pipe: NLUPipeline):
        '''
        Takes in a NLUPipeline and returns a list of missing  feature types types which would cause the pipeline to crash if not added
        If it is some kind of model that uses embeddings, it will check the metadata for that model
        and return a string with moelName@spark_nlp_storage_ref format

        It works in the following schema

        1. Get all feature provisions from the pipeline
        2. Get all feature requirements for pipeline
        3. Get missing requirements, by substracting provided from requirements, what is left are the missing features

        '''
        logger.info('Resolving missing components')
        pipe_requirements = [['sentence','token']]  # default requirements so we can support all output levels. minimal extra comoputation effort. If we add CHUNK here, we will aalwayshave POS default
        components_for_sentence_embedding_conversion = []
        pipe.has_trainable_components = False
        pipe_provided_features_withouth_storage_ref = []
        flat_provisions_with_storage_ref = []
        pipe_required_features_with_storage_ref = []
        missing_storage_refs = []

        components_for_ner_conversion = []
        components_for_chunk_embedding_conversion = []


        for component in pipe.components:
            trainable = PipelineQueryVerifier.is_untrained_model(component)
            if trainable: pipe.has_trainable_components = True
            # 1. Get all feature provisions from the pipeline
            logger.info(f"Getting Missing Feature for component={component.info.name}", )
            if not component.info.inputs == component.info.outputs:
                # edge case for components that provide token and require token and similar cases. I.e. Tokenizer/Normalizer/etc.
                pipe_provided_features_withouth_storage_ref.append(component.info.outputs)

            # 1.1 Get all storage ref feature provisions with @storage_ref notation from the pipeline for converters and providers of emebddings
            if PipelineQueryVerifier.has_storage_ref(component) and PipelineQueryVerifier.is_embedding_provider(component):
                flat_provisions_with_storage_ref.append(component.info.outputs[0] + '@' + PipelineQueryVerifier.extract_storage_ref(component))

            # 2. get all feature requirements for pipeline
            if PipelineQueryVerifier.has_embeddings_requirement(component) and not trainable and PipelineQueryVerifier.has_storage_ref(component):
                # We check if Storage ref is satisfied by some component and if it also is matched output_level_wise (checked by check_if_storage_ref_is_satisfied).
                # If there storage_ref is satisfied, we add a converter right away and update cols
                storage_ref = PipelineQueryVerifier.extract_storage_ref(component)
                storage_ref_satisfied, conversion_candidate = PipelineQueryVerifier.check_if_storage_ref_is_satisfied(component, pipe, storage_ref)
                if not storage_ref_satisfied and conversion_candidate is not None: components_for_sentence_embedding_conversion.append(conversion_candidate)

            for feature in component.info.inputs:
                if 'embed' in feature:
                    pipe_required_features_with_storage_ref.append(feature + '@' + storage_ref)
                else:
                    pipe_required_features_with_storage_ref.append(feature)
            pipe_requirements.append(pipe_required_features_with_storage_ref)
        else:
            pipe_requirements.append(component.info.inputs)





        # 3. get missing requirements, by substracting provided from requirements
        # Flatten lists, make them to sets and get missing components by substracting them.
        flat_requirements_with_storage_ref = set(item for sublist in pipe_requirements for item in sublist)
        flat_provisions_with_storage_ref = set(flat_provisions_with_storage_ref)
        flat_provisions_no_storage_ref = set(item for sublist in pipe_provided_features_withouth_storage_ref for item in sublist)

        # rmv spark identifier from provision
        flat_requirements_withouth_storage_ref = set(item.split('@')[0] if '@' in item else item for item in flat_requirements_with_storage_ref)

        # see what is missing, with identifier removed
        missing_components = PipelineQueryVerifier.clean_irrelevant_features(flat_requirements_withouth_storage_ref - flat_provisions_no_storage_ref)
        logger.info(f"Required columns with storage ref {pipe_required_features_with_storage_ref}", )
        logger.info(f"Required columns no ref flat {flat_requirements_withouth_storage_ref} ")
        logger.info(f"Required columns flat {flat_requirements_with_storage_ref} ")
        logger.info(f"Provided columns flat no ref {flat_provisions_no_storage_ref}", )
        logger.info(f"Provided columns flat  with storage ref {flat_provisions_with_storage_ref}", )

        logger.info(f"Missing columns no ref flat {missing_components}", )
        # since embeds are missing, we add embed with reference back
        if PipelineQueryVerifier.has_embeddings_requirement(flat_requirements_with_storage_ref) and not trainable:
            missing_storage_refs = PipelineQueryVerifier.clean_irrelevant_features(flat_requirements_with_storage_ref - flat_provisions_no_storage_ref- flat_provisions_with_storage_ref )
        logger.info(f"Missing columns no ref flat with storage refs {missing_storage_refs}", )

        # IF only @ in missing components, run the double checker with consults the namespace for storage ref match ups since not all storage_refs on a EmbeddingConsumer match up with storage ref of Embedding Provider
        if len(missing_components) == 0 and len(missing_storage_refs) == 0:
            logger.info(f'++++++++++++++++++No more components missing!++++++++++++++++++ \n {pipe}')
            return [], [],[]
        else:
            # we must recaclulate the difference, because we reoved the spark nlp reference previously for our set operation. Since it was not 0, we ad the Spark NLP rererence back
            logger.info(f'Components missing={missing_components} Storage Ref missing={missing_storage_refs}')
            return missing_components,missing_storage_refs, components_for_sentence_embedding_conversion

    @staticmethod
    def add_ner_converter_if_required(pipe: NLUPipeline) -> NLUPipeline:
        '''
        This method loops over every component in the pipeline and check if any of them outputs an NER type column.
        If NER exists in the pipeline, then this method checks if NER converter is already in pipeline.
        If NER exists and NER converter is NOT in pipeline, NER converter will be added to pipeline.
        :param pipe: The pipeline we wish to configure ner_converter dependency for
        :return: pipeline with NER configured
        '''

        ner_converter_exists = False
        ner_exists = False

        for component in pipe.components:
            if 'entities' in component.info.outputs: ner_converter_exists = True

        if ner_converter_exists == True:
            logger.info('NER converter already in pipeline')
            return pipe

        if not ner_converter_exists and ner_exists:
            logger.info('Adding NER Converter to pipeline')
            pipe.add(nlu.component_resolution.get_default_component_of_type(('ner_converter')))

        return pipe

    @staticmethod
    def add_sentence_embedding_converter(word_embedding_provider:SparkNLUComponent) -> SparkNLUComponent:
        """ Return a Word to Sentence Embedding converter for a given Component. The input cols with match the Sentence Embedder ones
            The converter is a NLU Component Embelishement of the Spark NLP Sentence Embeddings Annotator
        """
        logger.info(f'Adding Sentence embedding conversion for Embedding Provider={ word_embedding_provider.info.name}')

        c = nlu.Util(annotator_class='sentence_embeddings')
        storage_ref = PipelineQueryVerifier.extract_storage_ref(word_embedding_provider)
        c.model.setStorageRef(storage_ref)
        c.info.storage_ref = storage_ref
        embed_provider_col = word_embedding_provider.info.spark_output_column_names[0]
        c.model.setInputCols('document', )
        c.model.setOutputCol('sentence_embeddings@' + storage_ref)
        c.info.spark_input_column_names = ['document', embed_provider_col]
        c.info.input_column_names = ['document', embed_provider_col]

        c.info.spark_output_column_names = ['sentence_embeddings@' + storage_ref]
        c.info.output_column_names = ['sentence_embeddings@' + storage_ref]
        word_embedding_provider.info.storage_ref = storage_ref
        return c

    @staticmethod
    def add_chunk_embedding_converter(word_embedding_provider:SparkNLUComponent) -> SparkNLUComponent : # ner_converter_provider:SparkNLUComponent,
        """ Return a Word to CHUNK Embedding converter for a given Component. The input cols with match the Sentence Embedder ones
            The converter is a NLU Component Embelishement of the Spark NLP Sentence Embeddings Annotator
            The CHUNK embedder requires entities and also embeddings to generate data from. Since there could be multiple entities generators, we neeed to pass the correct one
        """

        logger.info(f'Adding Chunk embedding conversion for Embedding Provider={ word_embedding_provider.info.name} and NER Converter provider = ')
        entities_col = 'entities' # ner_converter_provider.info.spark_output_column_names[0]
        embed_provider_col = word_embedding_provider.info.spark_output_column_names[0]

        c = nlu.embeddings_chunker.EmbeddingsChunker(annotator_class='chunk_embedder')
        storage_ref = PipelineQueryVerifier.extract_storage_ref(word_embedding_provider)
        c.model.setStorageRef(storage_ref)
        c.info.storage_ref = storage_ref

        c.model.setInputCols(entities_col, embed_provider_col)
        c.model.setOutputCol('chunk_embeddings@' + storage_ref)
        c.info.spark_input_column_names = [entities_col, embed_provider_col]
        c.info.input_column_names = [entities_col, embed_provider_col]

        c.info.spark_output_column_names = ['chunk_embeddings@' + storage_ref]
        c.info.output_column_names = ['chunk_embeddings@' + storage_ref]
        return c






    @staticmethod
    def check_and_fix_nlu_pipeline(pipe: NLUPipeline) -> NLUPipeline:
        """Check if the NLU pipeline is ready to transform data and return it.
        If all dependencies not satisfied, returns a new NLU pipeline where dependencies and sub-dependencies are satisfied.

        Checks and resolves in the following order :


        1. Get a reference list of input features missing for the current pipe
        2. Resolve the list of missing features by adding new  Annotators to pipe
        3. Add NER Converter if required (When there is a NER model)
        4. Fix order and output column names
        5.

        :param pipe:
        :return:
        """
        # main entry point for Model stacking withouth pretrained pipelines
        # requirements and provided features will be lists of lists
        all_features_provided = False
        while all_features_provided == False:
            # After new components have been added, we must loop again and check for the new components if requriements are met
            components_to_add = []

            # Find missing components
            missing_components, missing_storage_refs, components_for_embedding_conversion = PipelineQueryVerifier.get_missing_required_features(pipe)
            logger.info(f"+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            logger.info(f"Trying to resolve missing features for \n missing_components={missing_components} \n missing storage_refs={missing_storage_refs}\n conversion_candidates={components_for_embedding_conversion}")

            if len(missing_components) ==0 and len (missing_storage_refs) == 0 and len(components_for_embedding_conversion) == 0: break  # Now all features are provided

            # Create missing base storage ref producers
            for missing_component in missing_storage_refs:
                components_to_add.append(nlu.component_resolution.get_default_component_of_type(missing_component, language=pipe.lang))


            # Create missing base components, storage refs are fetched in rpevious loop
            for missing_component in missing_components:
                if 'embed' in missing_component : continue
                components_to_add.append(nlu.component_resolution.get_default_component_of_type(missing_component, language=pipe.lang))
            # Create converters
            for c in components_for_embedding_conversion:
                if 'chunk' in c.name : converter =  PipelineQueryVerifier.add_chunk_embedding_converter(c)
                # elif 'sentence' in c.name:, default should always be sentence
                else : converter = PipelineQueryVerifier.add_sentence_embedding_converter(c)
                if converter is not None: components_to_add.append(converter)





            logger.info(f'Resolved for missing components the following NLU components : {components_to_add}')


            # Add missing components
            for new_component in components_to_add:
                pipe.add(new_component)
                logger.info(f'adding {new_component.info.name}')


            # 3 Add NER converter if NER component is in pipeline : (This is a bit ineficcent but it is most stable)
            # TODO in NLU HC either NER or NER converter internal
            # TODO Multi NER SCenario, each NER needs its own converter
            # todo add unique NER converter for each NER right away
            pipe = PipelineQueryVerifier.add_ner_converter_if_required(pipe)

        logger.info('Fixing column names')
        #  Validate naming of output columns is correct and no error will be thrown in spark
        pipe = PipelineQueryVerifier.check_and_fix_component_output_column_name_satisfaction(pipe)

        # 4.  fix order
        logger.info('Optimizing pipe component order')
        pipe = PipelineQueryVerifier.check_and_fix_component_order(pipe)

        # 5. Check if output column names overlap, if yes, fix
        # pipe = PipelineQueryVerifier.check_and_fix_component_order(pipe)
        # 6.  Download all file depenencies like train files or  dictionaries
        logger.info('Done with pipe optimizing')

        return pipe

    @staticmethod
    def extract_embed_level_identity(component, col='input'):
        """Figure out if component feeds on chunk/sent aka doc/word emb for either nput or output cols"""
        if col =='input':
            if any(filter(lambda s : 'document_embed' in s , component.info.inputs)): return 'document_embeddings'
            if any(filter(lambda s : 'sentence_embed' in s , component.info.inputs)): return 'sentence_embeddings'
            if any(filter(lambda s : 'chunk_embed' in s , component.info.inputs)): return 'chunk_embeddings'
            if any(filter(lambda s : 'token_embed' in s , component.info.inputs)): return 'token_embeddings'
        elif col == 'output':
            if any(filter(lambda s : 'document_embed' in s , component.info.outputs)): return 'document_embeddings'
            if any(filter(lambda s : 'sentence_embed' in s , component.info.outputs)): return 'sentence_embeddings'
            if any(filter(lambda s : 'chunk_embed' in s , component.info.outputs)): return 'chunk_embeddings'
            if any(filter(lambda s : 'token_embed' in s , component.info.outputs)): return 'token_embeddings'


    @staticmethod
    def is_matching_level(embedding_consumer, embedding_provider):
        """Check for embedding consumer if input level matches up outputlevel of consumer
        """

    @staticmethod
    def get_converters_provider_info(embedding_provider,pipe):
        """For a component and a pipe, find storage_ref and """

    @staticmethod
    def is_storage_ref_match(embedding_consumer, embedding_provider,pipe):
        """Check for 2 components, if one provides the embeddings for the other. Makes sure that output_level matches up (chunk/sent/tok/embeds)"""
        consumer_AT_ref = PipelineQueryVerifier.extract_storage_ref_AT_column(embedding_consumer,'input')
        provider_AT_rev = PipelineQueryVerifier.extract_storage_ref_AT_column(embedding_provider,'output')
        consum_level    = PipelineQueryVerifier.extract_embed_level_identity(embedding_consumer, 'input')
        provide_level   = PipelineQueryVerifier.extract_embed_level_identity(embedding_provider, 'output')

        consumer_ref    = PipelineQueryVerifier.nlu_extract_storage_ref_nlp_model(embedding_consumer)
        provider_rev    = PipelineQueryVerifier.nlu_extract_storage_ref_nlp_model(embedding_provider)

        # input/output levels must match
        if consum_level != provide_level : return False

        # If storage ref dont match up, we must consult the storage_ref_2_embed mapping if it still maybe is a match, otherwise it is not.
        if consumer_ref == provider_rev  : return True

        # Embed Components have have been resolved via@ have a  nlu_resolution_ref_source will match up with the consumer ref if correct embedding.
        if hasattr(embedding_provider.info, 'nlu_ref'):
            if consumer_ref == PipelineQueryVerifier.extract_storage_ref(embedding_provider.info.nlu_ref) : return True

        # If it is either  sentence_embedding_converter or chunk_embedding_converter then we gotta check what the storage ref of the inpot of those is.
        # If storage ref matches up, the providers output will match the consumer
        # if embedding_provider
        if embedding_provider.info.name in ["chunk_embedding_converter", 'sentence_embedding_converter']: # TODO FOR RESOLUTION
            nlu_ref, conv_prov_storage_ref = PipelineQueryVerifier.get_converters_provider_info(embedding_provider,pipe)


        return False

    @staticmethod
    def are_producer_consumer_matches(e_consumer:SparkNLUComponent,e_provider:SparkNLUComponent) -> bool:
        """Check for embedding_consumer and embedding_producer if they match storage_ref and output level wise wise """
        if PipelineQueryVerifier.extract_storage_ref(e_consumer)== PipelineQueryVerifier.extract_storage_ref(e_provider):
            if PipelineQueryVerifier.extract_embed_level_identity(e_consumer, 'input') ==  PipelineQueryVerifier.extract_embed_level_identity(e_provider, 'output'):
                return True
        return False


    @staticmethod
    def resolve_nlu_ref_2_storage_ref(nlu_ref):
        """For a given NLU ref search Namespace.licensed_storafe_ref_2_nlu_ref values. If there is a value match, return the key which is the storageRef this NLU ref is mapped to.
        IF no mapping exists, return ''
        """
        from nlu.namespace import NameSpace
        for k,v in NameSpace.licensed_storage_ref_2_nlu_ref.items():
            if v == nlu_ref: return k
        return ''

    @staticmethod
    def extract_embed_col(component):
        """Extract the exact name of the embed column in the component"""
        for c in component.info.spark_input_column_names:
            if 'embed' in c : return c
        return ''






    @staticmethod
    def check_and_fix_component_output_column_name_satisfaction(pipe: NLUPipeline):
        '''
        This function verifies that every input and output column name of a component is satisfied.
        If some output names are missing, it will be added by this methods.
        Usually classifiers need to change their input column name, so that it matches one of the previous embeddings because they have dynamic output names
        This function peforms the following steps :
        1. For each component we veryify that all input column names are satisfied  by checking all other components output names
        2. When a input column is missing we do the following :
        2.1 Figure out the type of the missing input column. The name of the missing column should be equal to the type
        2.2 Check if there is already a component in the pipe, which provides this input (It should)
        2.3. When A providing component is found, check if storage ref matches up.
        2.4 If True for all, update provider component output name, or update the original coponents input name
        :return: NLU pipeline where the output and input column names of the models have been adjusted to each other
        '''
        logger.info("Fixing input and output column names")
        for component_to_check in pipe.components:
            input_columns = set(component_to_check.info.spark_input_column_names)
            # a component either has '' storage ref or at most 1
            logger.info(f'Checking for component {component_to_check.info.name} wether inputs {input_columns} is satisfied by another component in the pipe ', )
            # TODO we must not only check if input satisfied, but if storage refs match! and Match Storage_refs accordingly
            for other_component in pipe.components:
                if component_to_check.info.name == other_component.info.name: continue

                output_columns = set(other_component.info.spark_output_column_names)
                input_columns -= output_columns # we substract alrfready provided columns

            input_columns = PipelineQueryVerifier.clean_irrelevant_features(input_columns)

            # Resolve basic mismatches, usually storage refs
            if len(input_columns) != 0 and not pipe.has_trainable_components or PipelineQueryVerifier.is_embedding_consumer(component_to_check):  # fix missing column name
                logger.info(f"Fixing bad input col for C={component_to_check} untrainable pipe")
                resolved_storage_ref_cols = []
                for missing_column in input_columns:
                    for other_component in pipe.components:
                        if component_to_check.info.name == other_component.info.name: continue
                        if other_component.info.type == missing_column:
                            # We update the output name for the component which consumes our feature

                            if PipelineQueryVerifier.has_storage_ref(other_component) and PipelineQueryVerifier.is_embedding_provider(component_to_check):
                                 if PipelineQueryVerifier.are_producer_consumer_matches(component_to_check,other_component):
                                     resolved_storage_ref_cols.append((other_component.info.spark_output_column_names[0],missing_column))

                            component_to_check.info.spark_output_column_names = [missing_column]
                            component_to_check.info.outputs = [missing_column]
                            logger.info(f'Resolved requirement for missing_column={missing_column} with inputs from provider={other_component.info.name} by col={missing_column} ')
                            other_component.model.setOutputCol(missing_column)


                for resolution, unsatisfied in resolved_storage_ref_cols:
                    component_to_check.info.spark_input_column_names.remove(unsatisfied)
                    component_to_check.info.spark_input_column_names.append(resolution)
                component_to_check.info.inputs = component_to_check.info.spark_input_column_names





            # Resolve training missatches
            elif len(input_columns) != 0 and pipe.has_trainable_components:  # fix missing column name
                logger.info(f"Fixing bad input col for C={component_to_check} trainable pipe")

                # for trainable components, we change their input columns and leave other components outputs unchanged
                for missing_column in input_columns:
                    for other_component in pipe.components:
                        if component_to_check.info.name == other_component.info.name: continue
                        if other_component.info.type == missing_column:
                            # We update the input col name for the componenet that has missing cols
                            component_to_check.info.spark_input_column_names.remove(missing_column)
                            # component_to_check.component_info.inputs.remove(missing_column)
                            # component_to_check.component_info.inputs.remove(missing_column)
                            # component_to_check.component_info.inputs.append(other_component.component_info.spark_output_column_names[0])

                            component_to_check.info.spark_input_column_names.append(
                                other_component.info.spark_output_column_names[0])
                            component_to_check.model.setInputCols(
                                component_to_check.info.spark_input_column_names)

                            logger.info(
                                f'Setting input col columns for component {component_to_check.info.name} to {other_component.info.spark_output_column_names[0]} ')

        return pipe

    @staticmethod
    def check_and_fix_component_output_column_name_overlap(pipe: NLUPipeline):
        '''
        #todo use?
        This method enforces that every component has a unique output column name.
        Especially for classifiers or bert_embeddings this issue might occur,


        1. For each component we veryify that all input column names are satisfied  by checking all other components output names
        2. When a input column is missing we do the following :
        2.1 Figure out the type of the missing input column. The name of the missing column should be equal to the type
        2.2 Check if there is already a component in the pipe, which provides this input (It should)
        2.3. When the providing component is found, update its output name, or update the original coponents input name
        :return: NLU pipeline where the output and input column names of the models have been adjusted to each other
        '''

        all_names_provided = False

        for component_to_check in pipe.components:
            all_names_provided_for_component = False
            input_columns = set(component_to_check.info.spark_input_column_names)
            logger.info(
                f'Checking for component {component_to_check.info.name} wether input {input_columns} is satisfied by another component in the pipe')
            for other_component in pipe.components:
                if component_to_check.info.name == other_component.info.name: continue
                output_columns = set(other_component.info.spark_output_column_names)
                input_columns -= output_columns  # set substraction

            input_columns = PipelineQueryVerifier.clean_irrelevant_features(input_columns)

            if len(input_columns) != 0:  # fix missing column name
                for missing_column in input_columns:
                    for other_component in pipe.components:
                        if component_to_check.info.name == other_component.info.name: continue
                        if other_component.info.type == missing_column:
                            # resolve which setter to use ...
                            # We update the output name for the component which provides our feature
                            other_component.info.spark_output_column_names = [missing_column]
                            logger.info(
                                f'Setting output columns for component {other_component.info.name} to {missing_column} ')
                            other_component.model.setOutputCol(missing_column)

        return pipe

    @staticmethod
    def check_and_fix_component_order(pipe: NLUPipeline):
        '''
        This method takes care that the order of components is the correct in such a way,
        that the pipeline can be iteratively processed by spark NLP.
        If output_level == Document, then sentence embeddings will be fed on Document col and classifiers recieve doc_embeds/doc_raw column, depending on if the classifier works with or withouth embeddings
        If output_level == sentence, then sentence embeddings will be fed on sentence col and classifiers recieve sentence_embeds/sentence_raw column, depending on if the classifier works with or withouth embeddings. IF sentence detector is missing, one will be added.

        '''
        logger.info("Starting to optimize component order ")
        correct_order_component_pipeline = []
        all_components_orderd = False
        all_components = pipe.components
        provided_features = []
        while all_components_orderd == False:
            for component in all_components:
                logger.info(f"Optimizing order for component {component.info.name}")
                input_columns = PipelineQueryVerifier.clean_irrelevant_features(component.info.spark_input_column_names)
                if set(input_columns).issubset(provided_features):
                    correct_order_component_pipeline.append(component)
                    if component in all_components: all_components.remove(component)
                    for feature in component.info.spark_output_column_names: provided_features.append(feature)
            if len(all_components) == 0: all_components_orderd = True

        pipe.components = correct_order_component_pipeline

        return pipe

    @staticmethod
    def configure_component_output_levels(pipe: NLUPipeline):
        '''
        This method configures sentenceEmbeddings and Classifier components to output at a specific level
        This method is called the first time .predit() is called and every time the output_level changed
        If output_level == Document, then sentence embeddings will be fed on Document col and classifiers recieve doc_embeds/doc_raw column, depending on if the classifier works with or withouth embeddings
        If output_level == sentence, then sentence embeddings will be fed on sentence col and classifiers recieve sentence_embeds/sentence_raw column, depending on if the classifier works with or withouth embeddings. IF sentence detector is missing, one will be added.

        '''
        if pipe.output_level == 'sentence':
            return PipelineQueryVerifier.configure_component_output_levels_to_sentence(pipe)
        elif pipe.output_level == 'document':
            return PipelineQueryVerifier.configure_component_output_levels_to_document(pipe)

    @staticmethod
    def configure_component_output_levels_to_sentence(pipe: NLUPipeline):
        '''
        Configure pipe compunoents to output level document
        :param pipe: pipe to be configured
        :return: configured pipe
        '''
        for c in pipe.components:
            if 'token' in c.info.spark_output_column_names: continue
            # if 'document' in c.component_info.inputs and 'sentence' not in c.component_info.inputs  :
            if 'document' in c.info.inputs and 'sentence' not in c.info.inputs and 'sentence' not in c.info.outputs:
                logger.info(f"Configuring C={c.info.name}  of Type={type(c.model)}")
                c.info.inputs.remove('document')
                c.info.inputs.append('sentence')
                # c.component_info.spark_input_column_names.remove('document')
                # c.component_info.spark_input_column_names.append('sentence')
                c.model.setInputCols(c.info.spark_input_column_names)

            if 'document' in c.info.spark_input_column_names and 'sentence' not in c.info.spark_input_column_names and 'sentence' not in c.info.spark_output_column_names:
                c.info.spark_input_column_names.remove('document')
                c.info.spark_input_column_names.append('sentence')
                if c.info.type == 'sentence_embeddings':
                    c.info.output_level = 'sentence'

        return pipe

    @staticmethod
    def configure_component_output_levels_to_document(pipe: NLUPipeline):
        '''
        Configure pipe compunoents to output level document
        :param pipe: pipe to be configured
        :return: configured pipe
        '''
        logger.info('Configuring components to document level')
        # Every sentenceEmbedding can work on Dcument col
        # This works on the assuption that EVERY annotator that works on sentence col, can also work on document col. Douple Tripple verify later
        # here we could change the col name to doc_embedding potentially
        # 1. Configure every Annotator/Classifier that works on sentences to take in Document instead of sentence
        #  Note: This takes care of changing Sentence_embeddings to Document embeddings, since embedder runs on doc then.
        for c in pipe.components:
            if 'token' in c.info.spark_output_column_names: continue
            if 'sentence' in c.info.inputs and 'document' not in c.info.inputs:
                logger.info(f"Configuring C={c.info.name}  of Type={type(c.model)} input to document level")
                c.info.inputs.remove('sentence')
                c.info.inputs.append('document')

            if 'sentence' in c.info.spark_input_column_names and 'document' not in c.info.spark_input_column_names:
                # if 'sentence' in c.component_info.spark_input_column_names : c.component_info.spark_input_column_names.remove('sentence')
                c.info.spark_input_column_names.remove('sentence')
                c.info.spark_input_column_names.append('document')
                c.model.setInputCols(c.info.spark_input_column_names)

            if c.info.type == 'sentence_embeddings':  # convert sentence embeds to doc
                c.info.output_level = 'document'

        return pipe

    @staticmethod
    def configure_output_to_most_recent(pipe: NLUPipeline):
        '''
        For annotators that feed on tokens, there are often multiple options of tokens they could feed on, i,e, spell/norm/lemma/stemm
        This method enforces that each annotator that takes in tokens will be fed the MOST RECENTLY ADDED token, unless specified in the NLU_load parameter otherwise

        :param pipe:
        :return:
        '''
        pass

    @staticmethod
    def has_sentence_emebddings_col(component):
        '''
        Check for a given component if it uses sentence embedding col
        :param component: component to check
        :return: True if uses raw sentences, False if not
        '''
        for inp in component.info.inputs:
            if inp == 'sentence_embeddings': return True
        return False

    @staticmethod
    def is_using_token_level_inputs(component):
        '''
        Check for a given component if it uses Token level input
        I.e. Lemma/stem/token/ and return the col name if so
        :param component: component to check
        :return: True if uses raw sentences, False if not
        '''
        token_inputs = ['token', 'lemma', 'stem', 'spell', '']
        for inp in component.info.inputs:
            if inp == 'sentence_embeddings': return True
        return False
